# Migrating Workspaces


## Migrating from TFE to TFE/TFC

## One Workspace at a Time Using Terraform CLI

You can move a state from one backend to another using the terraform backend block. This can be done to migrate state from one workspace to another, or any remote backend to another.

![state-migration-diagram-cli](/images/state-migration-cli.png)

1. Add the terraform backend block to your terraform code using the picture above as an example. `hostname`, `organization`, and `workspace` should correspend to the location of your existing state in TFC or TFE. If your remote state exists in an S3 bucket, or some other remote backend, refer to the documentation.
2. Run a `terraform init`
3. Replace the `hostname`, `organization`, and `workspace` with the new destination to migrate the state to.
4. Run `terraform init -migrate-state` 
5. Verify the state exists in the new workspace as expected

## Once Workspace at a Time Using TFE/TFC API

![state-migration-diagram-api](/images/state-migration-api.png)

Choose the workspace you wish to migrate from on the source TFE instance.

1. Login to your source TFE instance using the terraform cli 
  * For hosts with web browser capabilities: 
```
Terraform login my-tfe.example.com
```

  * For hosts without web browser capabilities, see here for documentation on configuring login credentials based on your OS:

https://www.terraform.io/cli/config/config-file#credentials


2. Set the environment variable `TFC_TOKEN` and `WORKSPACE_ID` from the source TFE instance and workspace

```
export TFC_TOKEN=”my api token 111ddd11aavvvbbb111”
export WORKSPACE_ID=”my workspace id”
```

  * Workspace ID can be found via the GUI by navigating to the workspaces "Settings" drop down and "General" option:

![workspace_id](/images/workspace_id.png)

  * Or you can use the API to find a workspaces ID. Paste the following into a script, replacing the fqdn, org, and workspace to match your query. 
 
```
#!/bin/bash

HTTP_RESPONSE=$(curl \
  --header "Authorization: Bearer $TFC_TOKEN" \
  --header "Content-Type: application/vnd.api+json" \
  https://josh2.is.tfe.rocks/api/v2/organizations/test-org-3/workspaces/org-3-workspace-1 | jq -r '.data | .id')

echo $HTTP_RESPONSE
```

3. Paste the following code into a bash script called getstate.sh, replacing the URL as needed, and `chmod +x getstate.sh`

```
#!/bin/bash

HTTP_RESPONSE=$(curl \
     --header "Authorization: Bearer "$TFC_TOKEN"" \
     --header "Content-Type: application/vnd.api+json" \
     "https://app.terraform.io/api/v2/workspaces/"$WORKSPACE_ID"/current-state-version" | jq -r '.data | .attributes | ."hosted-state-download-url"')

curl -o state.tfstate $HTTP_RESPONSE
```

4. Run `./getstate.sh` to download the state from the source TFE instance and workspace that you specified using environment variables in the previous step. The state will be placed in your working directory.

5. Modify / add  your workspaces terraform backend block to point to the new TFE/TFC hostname,
Org, and workspace.

```
terraform {
  backend "remote" {
    hostname = "josh2.is.tfe.rocks"
    organization = "test-org-3"

    workspaces {
      name = "org-3-workspace-1"
    }
  }
}
```

6. Run `terraform init -migrate-state` to connect the new state to the new workspace. 

7. Test the config my making a non-destructive resource change to verify proper functionality. 

# Resources

Using cloud-state-api https://learn.hashicorp.com/tutorials/terraform/cloud-state-api?in=terraform/cloud&utm_source=WEBSITE&utm_medium=WEB_IO&utm_offer=ARTICLE_PAGE&utm_content=DOCS
