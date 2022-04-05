terraform {
  backend "remote" {
    hostname = "my-tfe.example.com"
    organization = "test-org"

    workspaces {
      name = "test-workspace-1"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "example" {
  name     = "migration-test"
  location = "East US"
}
