#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
LAYER_DIR="$BUILD_DIR/layer"
ZIP_FILE="$BUILD_DIR/layer.zip"

echo "→ Création des dossiers..."
mkdir -p "$LAYER_DIR/python"

echo "→ Installation des dépendances via Docker..."
docker run --rm \
  -v "$LAYER_DIR:/output" \
  --entrypoint pip \
  public.ecr.aws/lambda/python:3.12 \
  install \
    requests pandas sqlalchemy psycopg2-binary \
    boto3 pytz numpy packaging reportlab \
    -t /output/python/

echo "→ Création du zip..."
cd "$LAYER_DIR"
zip -r "$ZIP_FILE" python/

echo "Layer buildé : $ZIP_FILE"