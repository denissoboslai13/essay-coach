"""Production entry point (used by the Docker image): the API under /api and the built
frontend at /, from one process and one origin.

In development, Vite serves the frontend and proxies /api to `app.main:app` instead.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.main import app as api
from app.main import lifespan

# A mounted app's lifespan does not run, so the outer app runs it
site = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
site.mount("/api", api)
site.mount("/", StaticFiles(directory=get_settings().frontend_dist, html=True), name="frontend")
