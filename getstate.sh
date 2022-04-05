#!/bin/bash

read -p "Did you set the TFC_TOKEN envioronment variable yet? (Y/N): " confirm && [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]] || exit 1

read -p "Enter the URL of the TFE/TFC instance. Example: tfe.mydomain.com: " URL
read -p "Enter ther WORKSPACE ID: " WORKSPACE_ID

HTTP_RESPONSE=$(curl \
--header "Authorization: Bearer "$TFC_TOKEN"" \
--header "Content-Type: application/vnd.api+json" \
"https://$URL/api/v2/workspaces/"$WORKSPACE_ID"/current-state-version" | jq -r '.data | .attributes | ."hosted-state-download-url"')

curl -o state.tfstate $HTTP_RESPONSE

