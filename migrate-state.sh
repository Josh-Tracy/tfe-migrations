#!/bin/bash

GREEN="\e[32m"
ENDCOLOR="\e[0m"

# Set source and dest variables
# SOURCE ORG API TOKEN
# TARGET USER API TOKEN
# SOURCE URL
# SOURCE ORG
# SOURCE WORKSPACE NAME
# TARGET URL
# TARGET WORKSPACE NAME

[[ -z "$SOURCE_ORG_TOKEN" ]] && echo "Please Set SOURCE_ORG_TOKEN to an API token" && exit 1
[[ -z "$TARGET_ORG_TOKEN" ]] && echo "Please Set TARGET_ORG_TOKEN to an API token" && exit 1
[[ -z "$TARGET_USER_TOKEN" ]] && echo "Please Set TARGET_ORG_TOKEN to an API token" && exit 1
[[ -z "$SOURCE_URL" ]] && echo "Please Set SOURCE_URL to the hostname of Terraform Enterprise/Cloud" && exit 1
[[ -z "$TARGET_URL" ]] && echo "Please Set TARGET_URL to the hostname of Terraform Enterprise/Cloud" && exit 1

# Get input for workspaces and variables if needed

# ----------------------------------------------------- #
# Get ID of workspaces provided
# ----------------------------------------------------- #

read -p "Enter the SOURCE_ORG_NAME name: " SOURCE_ORG
read -p "Enter the SOURCE_WORKSPACE_NAME name: " SOURCE_WORKSPACE_NAME

SOURCE_WORKSPACE_ID=$(curl \
  --header "Authorization: Bearer $SOURCE_ORG_TOKEN" \
  --header "Content-Type: application/vnd.api+json" \
  https://$SOURCE_URL/api/v2/organizations/$SOURCE_ORG/workspaces/$SOURCE_WORKSPACE_NAME | jq -r '.data | .id')

echo "The SOURCE_WORKSPACE_ID is: " $SOURCE_WORKSPACE_ID

read -p "Enter the TARGET_ORG_NAME name: " TARGET_ORG
read -p "Enter the TARGET_WORKSPACE_NAME name: " TARGET_WORKSPACE_NAME

TARGET_WORKSPACE_ID=$(curl \
  --header "Authorization: Bearer $TARGET_ORG_TOKEN" \
  --header "Content-Type: application/vnd.api+json" \
  https://$TARGET_URL/api/v2/organizations/$TARGET_ORG/workspaces/$TARGET_WORKSPACE_NAME | jq -r '.data | .id')

echo "The TARGET_WORKSPACE_ID is: " $TARGET_WORKSPACE_ID

# ----------------------------------------------------- #
# Download the state from the source workspace as state.tfstate
# ----------------------------------------------------- #

DOWNLOAD_RESPONSE=$(curl \
--header "Authorization: Bearer "$SOURCE_ORG_TOKEN"" \
--header "Content-Type: application/vnd.api+json" \
"https://$SOURCE_URL/api/v2/workspaces/"$SOURCE_WORKSPACE_ID"/current-state-version" | jq -r '.data | .attributes | ."hosted-state-download-url"')

curl -o state.tfstate $DOWNLOAD_RESPONSE

# ----------------------------------------------------- #
# Create the payload for upload to target workspace
# ----------------------------------------------------- #

echo "[INFO] Incrementing serial +1 from the original state's serial..."
OLD_STATE_SERIAL=$( cat state.tfstate | awk '/serial/ {print $2}' | sed 's/.$//')
NEW_STATE_SERIAL=$(($OLD_STATE_SERIAL+1))
echo "Incremented state serial is "$NEW_STATE_SERIAL

echo "[INFO] Creating md5 checksum..."
STATE_MD5SUM=$(md5sum state.tfstate | awk '{print $1}')

echo "md5 checksum is "$STATE_MD5SUM

echo "[INFO] Getting lineage from state.tfstate..."
STATE_LINEAGE=$( cat state.tfstate | awk '/lineage/ {print $2}' | sed 's/.$//')

echo "lineage is "$STATE_LINEAGE

echo "[INFO] Computing base64 content of state..."
STATE_BASE64=$(base64 state.tfstate)

ECHO "base64 content is "$STATE_BASE64

echo "[INFO] Creating payload.json in the working directory..."
cat > payload.json << EOF
 {
   "data": {
     "type":"state-versions",
     "attributes": {
       "serial": $NEW_STATE_SERIAL,
       "md5": "$STATE_MD5SUM",
       "lineage": $STATE_LINEAGE,
       "state": "$STATE_BASE64"
     }
   }
 }
EOF

# ----------------------------------------------------- #
# Lock Target Workspace
# ----------------------------------------------------- #

echo "[INFO] Locking the target workspace..."

LOCK_RESPONSE=$(curl \
  --header "Authorization: Bearer $TARGET_USER_TOKEN" \
  --header "Content-Type: application/vnd.api+json" \
  --request POST \
  --data @payload.json \
  https://$TARGET_URL/api/v2/workspaces/$TARGET_WORKSPACE_ID/actions/lock)

echo $LOCK_RESPONSE

# ----------------------------------------------------- #
# Upload payload to Target Workspace
# ----------------------------------------------------- #

echo -e $(printf "${GREEN} [INFO]--- A USER API TOKEN MUST BE USED TO UPLOAD STATE TO A LOCKED WORKSPACE, NOT AN ORG API TPKEN ---[INFO] ${ENDCOLOR}")

UPLOAD_RESPONSE=$(curl \
--header "Authorization: Bearer "$TARGET_USER_TOKEN"" \
--header "Content-Type: application/vnd.api+json" \
--request POST \
--data @payload.json \
https://$TARGET_URL/api/v2/workspaces/$TARGET_WORKSPACE_ID/state-versions)

echo $UPLOAD_RESPONSE