data "azurerm_client_config" "current" {}

locals {
  # ACR names allow only letters and digits and must be unique across Azure.
  acr_name = coalesce(
    var.acr_name,
    "${replace(var.prefix, "-", "")}${substr(sha256(data.azurerm_client_config.current.subscription_id), 0, 6)}"
  )

  # The subjects GitHub puts in its OIDC token. Jobs that declare an `environment:` get the
  # environment subject, every other job gets the branch subject.
  github_subjects = {
    env-dev     = "repo:${var.github_repository}:environment:azure-dev"
    env-prod    = "repo:${var.github_repository}:environment:azure-prod"
    branch-main = "repo:${var.github_repository}:ref:refs/heads/main"
    branch-dev  = "repo:${var.github_repository}:ref:refs/heads/dev"
  }
}

# -----------------------------------------------------------------------------------------------
# Resource group, registry and cluster
# -----------------------------------------------------------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = var.tags
}

resource "azurerm_container_registry" "main" {
  name                = local.acr_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.acr_sku
  admin_enabled       = false # images are pulled with managed identity, pushed with OIDC
  tags                = var.tags
}

resource "azurerm_kubernetes_cluster" "main" {
  name                = "${var.prefix}-aks"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  dns_prefix          = var.prefix
  kubernetes_version  = var.kubernetes_version
  tags                = var.tags

  oidc_issuer_enabled = true

  default_node_pool {
    name                        = "system"
    vm_size                     = var.node_vm_size
    node_count                  = var.node_count
    temporary_name_for_rotation = "systemtmp" # lets Terraform resize the pool without recreating the cluster
  }

  identity {
    type = "SystemAssigned"
  }

  # Entra ID sign-in with Azure RBAC for Kubernetes: who may do what in the cluster is managed with
  # Azure role assignments (see the GitHub deployer below) instead of kubeconfig certificates.
  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = data.azurerm_client_config.current.tenant_id
  }

  # Managed NGINX ingress controller. Its ingress class is webapprouting.kubernetes.azure.com.
  web_app_routing {
    dns_zone_ids = []
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
  }
}

# Nodes pull images from the registry with their own identity.
resource "azurerm_role_assignment" "kubelet_acr_pull" {
  scope                            = azurerm_container_registry.main.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
  skip_service_principal_aad_check = true
}

# -----------------------------------------------------------------------------------------------
# GitHub Actions deployer: OIDC federation, no stored secrets
# -----------------------------------------------------------------------------------------------
resource "azuread_application" "github" {
  display_name = "${var.prefix}-github-actions"
}

resource "azuread_service_principal" "github" {
  client_id = azuread_application.github.client_id
}

resource "azuread_application_federated_identity_credential" "github" {
  for_each = local.github_subjects

  application_id = azuread_application.github.id
  display_name   = "github-${each.key}"
  issuer         = "https://token.actions.githubusercontent.com"
  audiences      = ["api://AzureADTokenExchange"]
  subject        = each.value
}

# Push images.
resource "azurerm_role_assignment" "github_acr_push" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPush"
  principal_id         = azuread_service_principal.github.object_id
}

# `az aks get-credentials` needs permission to list the cluster user credentials.
resource "azurerm_role_assignment" "github_aks_user" {
  scope                = azurerm_kubernetes_cluster.main.id
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = azuread_service_principal.github.object_id
}

# Deploy into the cluster. The pipeline creates namespaces and applies Deployments, HPAs, Ingresses
# and a Secret, and namespaces are cluster-scoped, so it needs Cluster Admin. To narrow this down,
# pre-create the dev, prod and database namespaces once, drop the namespace step from the workflow
# and replace this role with "Azure Kubernetes Service RBAC Writer" assigned to each namespace
# (scope = "<cluster id>/namespaces/<name>").
resource "azurerm_role_assignment" "github_aks_deploy" {
  scope                = azurerm_kubernetes_cluster.main.id
  role_definition_name = "Azure Kubernetes Service RBAC Cluster Admin"
  principal_id         = azuread_service_principal.github.object_id
}
