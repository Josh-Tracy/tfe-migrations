terraform {
  backend "remote" {
    hostname = "app.terraform.io"
    organization = "example-org"

    workspaces {
      name = "example-workspace"
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
