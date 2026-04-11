#!/bin/bash
set -e

REGION="eu-north-1"
FUNCTION="velib-pipeline-prod-pipeline"
S3_BUCKET="velib-pipeline-prod-data"
SNS_ARN="arn:aws:sns:eu-north-1:503505393771:velib-pipeline-prod-alerts"
API_ENDPOINT="https://jeeuu4a70a.execute-api.eu-north-1.amazonaws.com"

# Charge .env
source ~/.env

echo " Copie des fichiers..."
cp ~/velib-data-pipeline/lambdas/pipeline/*.py ~/lambda-code/

echo "🗜️  Zip..."
cd ~/lambda-code
zip -r ~/pipeline-latest.zip . -q

echo " Déploiement Lambda code..."
aws lambda update-function-code \
  --function-name "$FUNCTION" \
  --zip-file fileb://~/pipeline-latest.zip \
  --region "$REGION" \
  --no-cli-pager > /dev/null

echo " Mise à jour variables d'environnement..."
aws lambda update-function-configuration \
  --function-name "$FUNCTION" \
  --environment "Variables={
    S3_BUCKET=$S3_BUCKET,
    SNS_ALERT_TOPIC_ARN=$SNS_ARN,
    AWS_REGION_NAME=$REGION,
    GROQ_API_KEY=$GROQ_API_KEY,
    POSTGRES_URL=$POSTGRES_URL
  }" \
  --region "$REGION" \
  --no-cli-pager > /dev/null

echo " Lancement du pipeline..."
aws lambda invoke \
  --function-name "$FUNCTION" \
  --region "$REGION" \
  --payload '{}' \
  ~/response.json

echo ""
cat ~/response.json
echo ""
echo " Terminé !"
echo " PDF : $API_ENDPOINT/download/report"
echo " CSV : $API_ENDPOINT/download/csv"