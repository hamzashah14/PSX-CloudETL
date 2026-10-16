# Values to copy into the GitHub repository settings (see README.md).

output "github_actions_client_id" {
  description = "Repository variable AZURE_CLIENT_ID"
  value       = azuread_application.github.client_id
}

output "tenant_id" {
  description = "Repository variable AZURE_TENANT_ID"
  value       = data.azurerm_client_config.current.tenant_id
}

output "subscription_id" {
  description = "Repository variable AZURE_SUBSCRIPTION_ID"
  value       = data.azurerm_client_config.current.subscription_id
}

output "resource_group_name" {
  description = "Repository variable AZURE_RESOURCE_GROUP"
  value       = azurerm_resource_group.main.name
}

output "aks_cluster_name" {
  description = "Repository variable AKS_CLUSTER_NAME"
  value       = azurerm_kubernetes_cluster.main.name
}

output "acr_name" {
  description = "Repository variable ACR_NAME"
  value       = azurerm_container_registry.main.name
}

output "acr_login_server" {
  description = "Registry host the images are pushed to"
  value       = azurerm_container_registry.main.login_server
}

output "get_credentials_command" {
  description = "Run this to use kubectl against the cluster from your own machine"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.main.name} --name ${azurerm_kubernetes_cluster.main.name} && kubelogin convert-kubeconfig -l azurecli"
}
