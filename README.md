# Migrating Workspaces

Migrating from one TFE instance to another TFE instance, from TFE to TFC, or from TFC to TFE can be accomplished multiple ways depending on what you are attempting to migrate.

* Migrating state between workspaces can be accomplished using the CLI or API.
* Migrating workspaces and configurations, modules, teams, and most other configruation settings can be accomplished using the API. 

## One Workspace at a Time Using Terraform CLI

You can move a state from one backend to another using the terraform backend block. This can be done to migrate state from one workspace to another, or any remote backend to another.

![state-migration-diagram-cli1](/images/state-migration-cli1.png)

1. Pull down the workspaces terraform repo.
2. Add the terraform backend block to your terraform code using the picture above as an example. `hostname`, `organization`, and `workspace` should correspend to the location of your existing state in TFC or TFE. If your remote state exists in an S3 bucket, or some other remote backend, refer to the documentation.
3. Run a `terraform init`
4. Replace the `hostname`, `organization`, and `workspace` with the new destination to migrate the state to.
5. Run `terraform init -migrate-state` 
6. Verify the state exists in the new workspace as expected

## One Workspace at a Time Using TFE/TFC API

![state-migration-diagram-api1](/images/state-migration-api1.png)

Choose the workspace you wish to migrate from on the source TFE instance.

1. Choose the source workspace you wish to migrate

2. Set the environment variable `TFC_TOKEN`, `TFE_URL`, and `WORKSPACE_ID` from the source TFE/TFC instance and workspace:

```
export TFC_TOKEN=”my api token 111ddd11aavvvbbb111”
export TFE_URL="my.tfe.com"
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

3. Paste the following code into a bash script called getstate.sh and `chmod +x getstate.sh`

```
#!/bin/bash

HTTP_RESPONSE=$(curl \
     --header "Authorization: Bearer "$TFC_TOKEN"" \
     --header "Content-Type: application/vnd.api+json" \
     "https://$TFE_URL/api/v2/workspaces/"$WORKSPACE_ID"/current-state-version" | jq -r '.data | .attributes | ."hosted-state-download-url"')

curl -o state.tfstate $HTTP_RESPONSE
```

4. Run `./getstate.sh` to download the state from the source TFE/TFC instance and workspace that you specified using environment variables in the previous step. The state will be placed in your working directory as `state.tfstate`.

5. Create and md5 checksum from the state file:

```
md5sum state.tfstate
```

6. Create base64 content of the state file:
```
base64 sate.tfstate
```

7. Note the lineage and serial from the original state file.

8. Create a file named `payload.json` with the following content. Replace the values in <> with the values computed in the earlier steps. Please note the value for the serial attribute should not be enclosed in double quotes since it is a JSON number.

```
 {
   "data": {
     "type":"state-versions",
     "attributes": {
       "serial": <SERIAL>,
       "md5": "<MD5_CHECKSUM>",
       "lineage": "<LINEAGE>",
       "state": "<BASE64_CONTENT>"
     }
   }
 }
 ```
9. Lock the target workspace you will be migrating state too.

10. Create a user API token from the user that locked the workspace. Export an environment variable called `TFC_USER_TOKEN`:

```
export TFC_USER_TOKEN="accccaaaa000011112222@"
```


> Note: Org level API tokens cannot upload state to a workspace.

11. Paste the following code into a bash script called upload-state-payload.sh  and `chmod +x upload-state-payload.sh`:

```
HTTP_RESPONSE=$(curl \
--header "Authorization: Bearer "$TFC_USER_TOKEN"" \
--header "Content-Type: application/vnd.api+json" \
--request POST \
--data @payload.json \
https://$URL/api/v2/workspaces/$WORKSPACE_ID/state-versions)

echo $HTTP_RESPONSE
```

12. Run the script and verify the state was uploaded to the new workspace. 


13. Test the config my making a non-destructive resource change to verify proper functionality by running terraform plan.

## Using the Scripts 

* TO DO

# Resources

Using cloud-state-api https://learn.hashicorp.com/tutorials/terraform/cloud-state-api?in=terraform/cloud&utm_source=WEBSITE&utm_medium=WEB_IO&utm_offer=ARTICLE_PAGE&utm_content=DOCS
