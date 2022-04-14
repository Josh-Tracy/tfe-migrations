#!/bin/bash
echo "[INFO]--- A USER API TOKEN MUST BE USED TO UPLOAD STATE TO A LOCKED WORKSPACE, NOT AN ORG API TPKEN ---[INFO]"
read -p "Did you set the TFC_USER_TOKEN envioronment variable yet? (Y/N): " confirm && [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]] || exit 1

read -p "Enter the URL of the TFE/TFC instance. Example: tfe.mydomain.com: " URL
read -p "Enter ther WORKSPACE ID: " WORKSPACE_ID

HTTP_RESPONSE=$(curl \
--header "Authorization: Bearer "$TFC_USER_TOKEN"" \
--header "Content-Type: application/vnd.api+json" \
--request POST \
--data @payload.json \
https://$URL/api/v2/workspaces/$WORKSPACE_ID/state-versions)

echo $HTTP_RESPONSE


