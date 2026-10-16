variable "subscription_id" {
  description = "Azure subscription to deploy into. Leave null to use ARM_SUBSCRIPTION_ID or the current `az account`."
  type        = string
  default     = null
}

variable "location" {
  description = "Azure region for every resource."
  type        = string
  default     = "westeurope"
}

variable "prefix" {
  description = "Name prefix for the resource group, the AKS cluster and the GitHub app registration."
  type        = string
  default     = "psx-etl"
}

variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to deploy through OIDC."
  type        = string
  default     = "hamzashah14/PSX-CloudETL"
}

variable "acr_name" {
  description = "Container registry name (5-50 letters and digits, globally unique). Leave null to derive one from the prefix and the subscription id."
  type        = string
  default     = null
}

variable "acr_sku" {
  description = "Container registry tier."
  type        = string
  default     = "Standard"
}

variable "kubernetes_version" {
  description = "AKS Kubernetes version. Leave null for the current AKS default."
  type        = string
  default     = null
}

variable "node_vm_size" {
  description = "VM size of the system node pool. A cheaper choice for a demo is Standard_B2s (burstable), at the cost of slower pods under load."
  type        = string
  default     = "Standard_D2s_v3"
}

variable "node_count" {
  description = "Number of nodes in the system node pool."
  type        = number
  default     = 2
}

variable "tags" {
  description = "Tags added to every resource that supports them."
  type        = map(string)
  default = {
    project    = "psx-etl"
    managed_by = "terraform"
  }
}
