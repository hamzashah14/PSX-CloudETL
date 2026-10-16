terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }

  # Local state by default. For a team, keep state in a storage account instead:
  #
  # backend "azurerm" {
  #   resource_group_name  = "tfstate-rg"
  #   storage_account_name = "<globally unique name>"
  #   container_name       = "tfstate"
  #   key                  = "psx-etl.tfstate"
  # }
}

provider "azurerm" {
  features {}
  # null = use ARM_SUBSCRIPTION_ID or the subscription selected with `az account set`
  subscription_id = var.subscription_id
}

provider "azuread" {}
