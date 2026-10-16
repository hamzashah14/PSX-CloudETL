# Infrastructure

Kubernetes manifests for the five services and PostgreSQL, built with
[kustomize](https://kubectl.docs.kubernetes.io/references/kustomize/) so one set of manifests serves
more than one cloud.

```
infra/
├── k8s/
│   ├── base/
│   │   ├── services/    Deployments, Services and autoscalers for extract, transform, load, scheduler, visualization
│   │   ├── database/    PostgreSQL StatefulSet and Service (namespace: database)
│   │   └── ingress/     routes shared by every cloud: no host, no ingress class
│   ├── overlays/
│   │   ├── ibm/         IBM Cloud Kubernetes Service: Container Registry images, IBM ingress class and host
│   │   └── azure/       Azure Kubernetes Service: Azure Disk data directory, application routing ingress
│   └── examples/        postgres-secret.example.yaml, a reference only, never applied
└── scripts/
    └── create-db-secret.sh
```

Each overlay has three parts (`database`, `services`, `ingress`) because they go into different
namespaces: the database into `database`, everything else into the target namespace (`dev` or `prod`).

## Deploying by hand

```bash
export POSTGRES_USER=etluser POSTGRES_PASSWORD='choose-a-password' POSTGRES_DB=etldb
infra/scripts/create-db-secret.sh database dev            # 1. secret, in both namespaces

kubectl apply -k infra/k8s/overlays/ibm/database -n database   # 2. database
kubectl apply -k infra/k8s/overlays/ibm/services -n dev        # 3. services and autoscalers
kubectl apply -k infra/k8s/overlays/ibm/ingress  -n dev        # 4. ingress
```

Use `overlays/azure` for AKS. The Azure overlay does not know your registry, so point the images at it
first (the GitHub Actions workflow does this for you):

```bash
cd infra/k8s/overlays/azure/services
kustomize edit set image psx-etl-extract=<acr>.azurecr.io/psx-etl-extract:<tag>   # repeat for each service
```

To see exactly what would be applied: `kubectl kustomize infra/k8s/overlays/azure/services`.

## Decisions worth knowing

- **The database password is not in Git.** `create-db-secret.sh` reads it from the environment (Jenkins
  credentials or GitHub environment secrets) and creates `postgres-secret` in the database namespace
  and in the application namespace, because a pod can only read secrets from its own namespace. A
  committed placeholder secret would be applied over the real password on every deploy.
- **Autoscaling.** extract, transform, load and visualization each have a CPU-based
  HorizontalPodAutoscaler (1 to 3 replicas, 70% of the CPU request). It needs metrics-server, which both
  IBM Cloud Kubernetes Service and AKS install. Their Deployments do not set `replicas`, so a deploy
  never resets the count the autoscaler chose.
- **The scheduler is never scaled.** It starts a pipeline run every 30 seconds, so a second copy would
  double every run. It is pinned to one replica with the `Recreate` strategy so the old and the new
  scheduler never overlap during a rollout.
- **Storage.** Both overlays use the cluster's default storage class. Azure disks contain a `lost+found`
  folder in the root, which stops PostgreSQL from initialising, so the Azure overlay moves `PGDATA` to a
  sub-folder. The IBM overlay leaves it alone on purpose: changing it on an existing volume would start
  an empty database next to the old data.
- **Azure ingress** uses the AKS application routing add-on (`webapprouting.kubernetes.azure.com`). With
  no host set, the dashboard is reachable on the ingress IP. For a domain and HTTPS, add a `host` and a
  `tls` section (a certificate from Key Vault or cert-manager) to the ingress patch.

## Tests

`tests/infra_tests` renders every overlay with `kubectl kustomize` (no cluster needed; skipped when
kubectl is missing) and checks the rules above: no Secret in any manifest, requests and probes on every
Deployment, autoscalers only on the stateless services, a single `Recreate` scheduler, services matching
their Deployments, the right images, ingress class and routes per cloud, and the Postgres probes and
`PGDATA` per cloud. It also runs the secret script against a fake kubectl to check URL encoding and that no
password reaches a command line.
