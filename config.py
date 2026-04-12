import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
API_ENDPOINT = os.environ.get("API_ENDPOINT", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "velib-pipeline-prod-data")

SOURCE_API = "API Velib' (temps reel)"
SOURCE_S3 = "AWS S3 (dernier snapshot)"
PARIS_TIMEZONE = "Europe/Paris"