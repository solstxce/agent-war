"""Lazy Firestore initialization. Cloud connections use Application Default Credentials."""

import os
from functools import lru_cache

import firebase_admin
from firebase_admin import firestore
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore import Client

from logistics_api.config import get_settings


@lru_cache
def get_firestore_client() -> Client:
    settings = get_settings()
    if not settings.firebase_project_id:
        raise RuntimeError("Set FIREBASE_PROJECT_ID before accessing Firestore.")
    if settings.firestore_emulator_host:
        if settings.app_environment != "development":
            raise RuntimeError("Firestore emulator is only supported in development.")
        os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host
        return Client(project=settings.firebase_project_id, credentials=AnonymousCredentials())
    try:
        app = firebase_admin.get_app("logistics")
    except ValueError:
        app = firebase_admin.initialize_app(
            options={"projectId": settings.firebase_project_id}, name="logistics"
        )
    return firestore.client(app=app)
