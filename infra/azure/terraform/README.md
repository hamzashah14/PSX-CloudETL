# Azure infrastructure (AKS + ACR + GitHub deployer)

Terraform for everything the Azure deployment workflow (`.github/workflows/azure.yml`) needs:

| Resource | Purpose |
|----------|---------|
| Resource group `<prefix>-rg` | Holds everything below, so `terraform destroy` removes it all |
| Azure Container Registry (Standard, admin user disabled) | Stores the five service images |
| AKS cluster `<prefix>-aks` | System node pool (default 2 x `Standard_D2s_v3`), Entra ID sign-in with Azure RBAC, OIDC issuer, managed NGINX ingress (`web_app_routing`, ingress class `webapprouting.kubernetes.azure.com`) |
| `AcrPull` for the kubelet identity | Nodes pull images without any registry password |
| Entra ID app registration + service principal `<prefix>-github-actions` | The identity GitHub Actions signs in as |
| 4 federated credentials | Lets GitHub sign in with a short-lived OIDC token (no stored secret): `environment:azure-dev`, `environment:azure-prod`, `ref:refs/heads/main`, `ref:refs/heads/dev` |
| Roles for the deployer | `AcrPush` on the registry, `Azure Kubernetes Service Cluster User Role` and `Azure Kubernetes Service RBAC Cluster Admin` on the cluster |

The workflow's `build` and `scan` jobs have no GitHub environment, so GitHub identifies them by branch (`main` or `dev`). The `deploy` job runs in an environment (`azure-dev` or `azure-prod`) and is identified by that. Running the workflow manually from any other branch is rejected by Azure.

**Why Cluster Admin?** The deploy job creates the `database`, `dev` and `prod` namespaces and applies Deployments, HPAs, Ingresses and a Secret, and namespaces are cluster-scoped. To narrow it down, create the three namespaces once, remove the namespace step from the workflow and replace the Cluster Admin assignment with `Azure Kubernetes Service RBAC Writer` assigned per namespace (scope `<cluster id>/namespaces/<name>`).

## Prerequisites

- An Azure subscription where you may create resources **and** role assignments (Owner, or Contributor plus User Access Administrator)
- Permission to create app registrations in Entra ID (the *Application Developer* role is enough)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), [Terraform](https://developer.hashicorp.com/terraform/install) 1.5 or newer

## Create it

```bash
az login
az account set --subscription "<subscription id>"

cd infra/azure/terraform
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

Optional settings go in a `terraform.tfvars` file (git-ignored), for example:

```hcl
location     = "centralindia"
node_vm_size = "Standard_B2s"   # about a third of the price of a D2s_v3, slower under load
node_count   = 2
```

## Cost warning

The two AKS nodes are billed for every hour they exist, whether or not anything runs on them. Rough order of magnitude for the defaults: **60 to 150 USD per month** depending on region and VM size, plus the Standard registry (about 20 USD per month) and a public load balancer for the ingress. Check the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/) for your region, and **run `terraform destroy` when you are done**:

```bash
terraform destroy
```

## Connect GitHub

`terraform output` prints every value the repository needs.

**Repository variables** (Settings > Secrets and variables > Actions > Variables). They are not secret:

| Variable | From |
|----------|------|
| `AZURE_CLIENT_ID` | `github_actions_client_id` |
| `AZURE_TENANT_ID` | `tenant_id` |
| `AZURE_SUBSCRIPTION_ID` | `subscription_id` |
| `AZURE_RESOURCE_GROUP` | `resource_group_name` |
| `AKS_CLUSTER_NAME` | `aks_cluster_name` |
| `ACR_NAME` | `acr_name` |

**Environments** (Settings > Environments):

| Environment | Setup |
|-------------|-------|
| `azure-dev` | No protection rules. Used by manual runs that pick `dev`. |
| `azure-prod` | Add **Required reviewers**: this is the approval gate. A manual run that picks `prod` (only allowed from `main`) builds and scans the images, then waits here until a reviewer approves. Restrict deployment branches to `main` if you like. |

**Environment secrets** (add them to both environments; use different values for prod). They create the database secret in the cluster, which is no longer stored in Git:

| Secret | Meaning |
|--------|---------|
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password: choose a strong one |
| `POSTGRES_DB` | Database name |

No Azure password or client secret is stored anywhere: the workflow signs in with OIDC.

## Use the cluster from your machine

```bash
$(terraform output -raw get_credentials_command)
kubectl get nodes
```

The command also runs `kubelogin convert-kubeconfig`, which AKS clusters with Azure RBAC need. Install kubelogin with `az aks install-cli`.

## Ingress address

After the first deploy:

```bash
kubectl get ingress -n prod
```

The managed ingress controller gets a public IP. The Ingress has no host name by default, so the dashboard answers on `http://<that ip>/`. For a real domain and TLS, add a host to the Azure ingress overlay and an Azure DNS zone or cert-manager.

## State

State is stored locally in `terraform.tfstate`. Keep it safe (it is git-ignored) or move it to a storage account with the commented `backend "azurerm"` block in `versions.tf` before sharing this with anyone else.
