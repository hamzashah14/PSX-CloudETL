"""Renders every kustomize overlay with `kubectl kustomize` (no cluster needed) and checks the
invariants the deployments rely on. Skipped when kubectl is not installed."""
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
OVERLAYS = ROOT / "infra" / "k8s" / "overlays"
CLOUDS = ["ibm", "azure"]
PARTS = ["database", "services", "ingress"]
SERVICES = {"extract": 8000, "transform": 8001, "load": 8003, "scheduler": 8004, "visualization": 8002}
SCALED = ["extract", "transform", "load", "visualization"]  # the scheduler must stay a single copy

pytestmark = pytest.mark.skipif(shutil.which("kubectl") is None, reason="kubectl is not installed")


def render(cloud, part):
    out = subprocess.run(
        ["kubectl", "kustomize", str(OVERLAYS / cloud / part)], capture_output=True, text=True, check=True
    ).stdout
    return [d for d in yaml.safe_load_all(out) if d]


def of_kind(docs, kind):
    return {d["metadata"]["name"]: d for d in docs if d["kind"] == kind}


@pytest.fixture(scope="module", params=CLOUDS)
def cloud(request):
    return request.param


@pytest.mark.parametrize("part", PARTS)
def test_every_overlay_renders(cloud, part):
    assert render(cloud, part)


def test_no_secret_is_committed(cloud):
    # the database password comes from infra/scripts/create-db-secret.sh, never from a manifest
    for part in PARTS:
        assert not of_kind(render(cloud, part), "Secret")
    assert not list((ROOT / "infra" / "k8s").rglob("*secret*.yaml")) or all(
        "examples" in p.parts for p in (ROOT / "infra" / "k8s").rglob("*secret*.yaml")
    )


def test_every_deployment_has_requests_and_probes(cloud):
    deployments = of_kind(render(cloud, "services"), "Deployment")
    assert sorted(deployments) == sorted(f"{s}-deployment" for s in SERVICES)
    for name, d in deployments.items():
        c = d["spec"]["template"]["spec"]["containers"][0]
        assert c["resources"]["requests"]["cpu"], name  # an HPA cannot work without a CPU request
        assert c["readinessProbe"] and c["livenessProbe"], name
        assert c["ports"][0]["containerPort"] == SERVICES[name.split("-")[0]], name


def test_load_liveness_does_not_depend_on_the_database(cloud):
    # Load's /health fails (503) when the database is down. As a readiness probe that stops traffic, as a
    # liveness probe it would restart the pod in a loop without fixing anything.
    c = of_kind(render(cloud, "services"), "Deployment")["load-deployment"]["spec"]["template"]["spec"]["containers"][0]
    assert c["readinessProbe"]["httpGet"]["path"] == "/health"
    assert "httpGet" not in c["livenessProbe"] and c["livenessProbe"]["tcpSocket"]["port"] == 8003


def test_autoscaling_covers_the_stateless_services_only(cloud):
    docs = render(cloud, "services")
    deployments, hpas = of_kind(docs, "Deployment"), of_kind(docs, "HorizontalPodAutoscaler")
    assert sorted(h["spec"]["scaleTargetRef"]["name"] for h in hpas.values()) == sorted(f"{s}-deployment" for s in SCALED)
    for h in hpas.values():
        assert h["spec"]["scaleTargetRef"]["name"] in deployments
        assert h["spec"]["minReplicas"] >= 1 and h["spec"]["maxReplicas"] > h["spec"]["minReplicas"]
        assert h["spec"]["metrics"][0]["resource"]["name"] == "cpu"
    for s in SCALED:  # the HPA owns the replica count, so the Deployment must not pin it on every apply
        assert "replicas" not in deployments[f"{s}-deployment"]["spec"], s


def test_scheduler_is_a_singleton_that_is_never_duplicated(cloud):
    sched = of_kind(render(cloud, "services"), "Deployment")["scheduler-deployment"]["spec"]
    assert sched["replicas"] == 1
    assert sched["strategy"]["type"] == "Recreate"  # old and new scheduler must not overlap during a rollout


def test_service_selectors_match_their_deployments(cloud):
    docs = render(cloud, "services")
    deployments, services = of_kind(docs, "Deployment"), of_kind(docs, "Service")
    for s, port in SERVICES.items():
        svc = services[f"{s}-service"]["spec"]
        assert svc["ports"][0]["port"] == port and svc["ports"][0]["targetPort"] == port
        labels = deployments[f"{s}-deployment"]["spec"]["template"]["metadata"]["labels"]
        assert all(labels.get(k) == v for k, v in svc["selector"].items()), s


def test_images_follow_the_cloud_registry():
    ibm = of_kind(render("ibm", "services"), "Deployment")
    azure = of_kind(render("azure", "services"), "Deployment")
    for s in SERVICES:
        image = lambda docs: docs[f"{s}-deployment"]["spec"]["template"]["spec"]["containers"][0]["image"]  # noqa: E731
        assert image(ibm) == f"icr.io/etl-registry/psx-etl-{s}:{s}-latest"  # the tag the Jenkins build pushes
        assert image(azure) == f"psx-etl-{s}:latest"  # CI points these at the ACR with `kustomize edit set image`


def test_ingress_routes_to_real_services_and_ports(cloud):
    ingresses = of_kind(render(cloud, "ingress"), "Ingress")
    assert sorted(ingresses) == sorted(f"{s}-ingress" for s in ["visualization", "scheduler", "transform", "load", "extract"])
    for ing in ingresses.values():
        for rule in ing["spec"]["rules"]:
            for path in rule["http"]["paths"]:
                backend = path["backend"]["service"]
                name = backend["name"].replace("-service", "")
                assert backend["port"]["number"] == SERVICES[name], (ing["metadata"]["name"], backend)


def test_ingress_class_and_host_per_cloud():
    ibm = of_kind(render("ibm", "ingress"), "Ingress")
    azure = of_kind(render("azure", "ingress"), "Ingress")
    for ing in ibm.values():
        assert ing["spec"]["ingressClassName"] == "public-iks-k8s-nginx"
        assert ing["spec"]["rules"][0]["host"].endswith(".containers.appdomain.cloud")
        assert ing["metadata"]["annotations"]["nginx.ingress.kubernetes.io/ssl-redirect"] == "true"
    for ing in azure.values():
        assert ing["spec"]["ingressClassName"] == "webapprouting.kubernetes.azure.com"
        assert "host" not in ing["spec"]["rules"][0]  # reachable on the ingress IP until a domain is added
        assert "ssl-redirect" not in ing["metadata"].get("annotations", {})  # no certificate yet, so no forced redirect


def test_database_probes_use_the_secret_not_hard_coded_names(cloud):
    docs = render(cloud, "database")
    sts = of_kind(docs, "StatefulSet")["postgres"]
    assert sts["metadata"]["namespace"] == "database"
    c = sts["spec"]["template"]["spec"]["containers"][0]
    for probe in (c["livenessProbe"], c["readinessProbe"]):
        command = " ".join(probe["exec"]["command"])
        assert "$POSTGRES_USER" in command and "$POSTGRES_DB" in command and "psx_" not in command
    # no stand-alone PVC: the StatefulSet's volumeClaimTemplates create the volume
    assert not of_kind(docs, "PersistentVolumeClaim")


def test_azure_database_uses_a_pgdata_subfolder_ibm_keeps_its_existing_layout():
    def env(cloud):
        c = of_kind(render(cloud, "database"), "StatefulSet")["postgres"]["spec"]["template"]["spec"]["containers"][0]
        return {e["name"]: e.get("value") for e in c.get("env", [])}

    # Azure disks have lost+found in the root, which breaks initdb. Changing PGDATA on the existing IBM
    # volume would start an empty database next to the old data, so only Azure gets it.
    assert env("azure").get("PGDATA") == "/var/lib/postgresql/data/pgdata"
    assert "PGDATA" not in env("ibm")
