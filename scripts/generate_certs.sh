#!/bin/bash
set -e
mkdir -p certs
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout certs/server.key \
  -out certs/server.crt \
  -subj "/CN=engram.local" \
  -addext "subjectAltName=DNS:engram.local,DNS:localhost,IP:127.0.0.1"
echo "Certificates generated in certs/"
