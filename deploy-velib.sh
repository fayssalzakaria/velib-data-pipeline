#!/bin/bash
set -e

REGION="eu-north-1"
FUNCTION="velib-pipeline-prod-pipeline"
S3_BUCKET="velib-pipeline-prod-data"
SNS_ARN="arn:aws:sns:eu-north-1:503505393771:velib-pipeline-prod-alerts"

source ~/.env

# Recupere les endpoints automatiquement depuis Terraform
echo "Recuperation des endpoints Terraform..."
cd ~/velib-data-pipeline/infrastructure
AURORA_ENDPOINT=$(terraform output -raw aurora_endpoint 2>/dev/null)
API_ENDPOINT=$(terraform output -raw api_endpoint 2>/dev/null)
POSTGRES_URL="postgresql://velib_app:${DB_PASSWORD}@${AURORA_ENDPOINT}/velib"

echo "Aurora : $AURORA_ENDPOINT"
echo "API    : $API_ENDPOINT"

echo "Copie des fichiers..."
cp ~/velib-data-pipeline/lambdas/pipeline/*.py ~/lambda-code/

echo "Zip..."
cd ~/lambda-code
zip -r ~/pipeline-latest.zip . -q

echo "Deploiement Lambda code..."
aws lambda update-function-code \
  --function-name "$FUNCTION" \
  --zip-file fileb://~/pipeline-latest.zip \
  --region "$REGION" \
  --no-cli-pager > /dev/null

echo "Attente fin de mise a jour code..."
aws lambda wait function-updated \
  --function-name "$FUNCTION" \
  --region "$REGION"

echo "Mise a jour variables..."
cat > /tmp/env-vars.json << EOF
{
  "Variables": {
    "S3_BUCKET": "$S3_BUCKET",
    "SNS_ALERT_TOPIC_ARN": "$SNS_ARN",
    "AWS_REGION_NAME": "$REGION",
    "GROQ_API_KEY": "$GROQ_API_KEY",
    "POSTGRES_URL": "$POSTGRES_URL"
  }
}
EOF

aws lambda update-function-configuration \
  --function-name "$FUNCTION" \
  --environment file:///tmp/env-vars.json \
  --region "$REGION" \
  --no-cli-pager > /dev/null

echo "Attente fin de mise a jour config..."
aws lambda wait function-updated \
  --function-name "$FUNCTION" \
  --region "$REGION"

echo "Lancement pipeline..."
aws lambda invoke \
  --function-name "$FUNCTION" \
  --region "$REGION" \
  --payload '{}' \
  ~/response.json

echo ""
cat ~/response.json
echo ""
echo "Termine !"
echo "PDF : $API_ENDPOINT/download/report"
echo "CSV : $API_ENDPOINT/download/csv"