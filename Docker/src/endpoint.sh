#!/usr/bin/env sh

set -e
set -o pipefail

TARGET_DIR=$1
OUTPUT_FILE=$2

echo "### Run kustomize command ###"
echo ""
echo ""

/template  -m siim-dev-lma.yaml 