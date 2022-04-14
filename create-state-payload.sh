#!/bin/bash

read -p "Enter the serial. Should be incremented by 1 from the original state serial: " SERIAL

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
       "serial": $SERIAL,
       "md5": "$STATE_MD5SUM",
       "lineage": $STATE_LINEAGE,
       "state": "$STATE_BASE64"
     }
   }
 }
EOF


