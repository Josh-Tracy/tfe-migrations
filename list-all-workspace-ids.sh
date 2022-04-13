#!/bin/bash

read -p "Did you set the TFC_TOKEN envioronment variable yet? (Y/N): " confirm && [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]] || exit 1

read -p "Enter the URL of the TFE/TFC instance. Example: tfe.mydomain.com: " URL
read -p "Enter the ORG name that contains the workspaces: " ORG

HTTP_RESPONSE=$(curl \
  --header "Authorization: Bearer $TFC_TOKEN" \
  --header "Content-Type: application/vnd.api+json" \
  https://$URL/api/v2/organizations/$ORG/workspaces?page%5Bnumber%5D=1\u0026page%5Bsize%5D=100 | jq -r '.data[] | .id')

echo $HTTP_RESPONSE