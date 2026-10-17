"""Lazy Firebase initialization with explicit development-only emulator access."""
import os
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore import Client

from logistics_api.config import get_settings


def guard_emulators() -> None:
    settings = get_settings()
    if settings.app_environment != "development" and any((settings.firestore_emulator_host, settings.firebase_auth_emulator_host, os.getenv("FIRESTORE_EMULATOR_HOST"), os.getenv("FIREBASE_AUTH_EMULATOR_HOST"))):
        raise RuntimeError("Firebase emulators are only supported in development")
    firestore_host = settings.firestore_emulator_host or os.getenv("FIRESTORE_EMULATOR_HOST", "")
    auth_host = settings.firebase_auth_emulator_host or os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "")
    if bool(firestore_host) != bool(auth_host):
        raise RuntimeError("Configure Auth and Firestore emulators together; do not mix emulator authentication with cloud data")
    if settings.firebase_auth_emulator_host:
        os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = settings.firebase_auth_emulator_host
    if settings.firestore_emulator_host:
        os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host


@lru_cache
def get_firebase_app():
    settings = get_settings()
    guard_emulators()
    if not settings.firebase_project_id:
        raise RuntimeError("Firebase project is not configured")
    try:
        return firebase_admin.get_app("logistics")
    except ValueError:
        credential = credentials.Certificate(settings.google_application_credentials) if settings.google_application_credentials else None
        return firebase_admin.initialize_app(credential=credential, options={"projectId": settings.firebase_project_id}, name="logistics")


@lru_cache
def get_firestore_client() -> Client:
    settings = get_settings()
    guard_emulators()
    if not settings.firebase_project_id:
        raise RuntimeError("Firebase project is not configured")
    if settings.firestore_emulator_host:
        return Client(project=settings.firebase_project_id, credentials=AnonymousCredentials())
    return firestore.client(app=get_firebase_app())
