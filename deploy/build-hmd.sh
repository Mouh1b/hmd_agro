#!/bin/bash
# Build the HMD Agro production image from apps.json. Usage: ./build-hmd.sh [tag]
set -e

TAG="${1:-v15}"

DOCKER_BUILDKIT=1 docker build \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-15 \
  --secret id=apps_json,src=apps.json \
  --tag=hmd-agro-prod:${TAG} \
  --file=images/layered/Containerfile .
