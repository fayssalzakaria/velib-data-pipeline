from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware
from airflow.www.app import create_app
from api.download_api import router as download_router


app = FastAPI()

# Intègre l’API perso sous /api
app.include_router(download_router, prefix="/api")

# Monte l’interface Airflow à la racine
app.mount("/", WSGIMiddleware(create_app()))
