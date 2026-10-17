"""Authenticated operational API. Every operation is scoped by stored membership."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from google.cloud import firestore
from pydantic import BaseModel, ConfigDict, Field, model_validator

from logistics_api.firebase import get_firebase_app, get_firestore_client

router = APIRouter(prefix="/api", tags=["operations"])
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Firebase authentication required")
    try:
        firebase_app = get_firebase_app()
    except Exception:
        raise HTTPException(503, "Authentication service unavailable; configure backend Firebase credentials") from None
    try:
        token = auth.verify_id_token(credentials.credentials, app=firebase_app, check_revoked=True)
        if not token.get("uid") or "/" in token["uid"]:
            raise auth.InvalidIdTokenError("Unsupported user identifier")
        return token
    except (auth.InvalidIdTokenError, auth.ExpiredIdTokenError, auth.RevokedIdTokenError, ValueError):
        raise HTTPException(401, "Invalid or expired authentication token") from None
    except Exception:
        raise HTTPException(503, "Authentication service unavailable") from None


def database():
    try:
        return get_firestore_client()
    except Exception:
        raise HTTPException(503, "Database unavailable; check server Firebase configuration") from None


def member(org_id: str, user: dict, db) -> str:
    snapshot = db.collection("organizations").document(org_id).collection("members").document(user["uid"]).get(timeout=10, retry=None)
    if not snapshot.exists or snapshot.to_dict().get("role") not in {"owner", "dispatcher"}:
        raise HTTPException(403, "Dispatcher workspace membership required")
    return snapshot.to_dict()["role"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Workspace(StrictModel):
    name: str = Field(min_length=1, max_length=120)


class Coordinates(StrictModel):
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode="after")
    def paired_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be supplied together")
        return self


class Delivery(Coordinates):
    customer_name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=1000)
    load_kg: float = Field(gt=0, le=100000, allow_inf_nan=False)
    window_start: datetime | None = None
    window_end: datetime | None = None
    status: Literal["pending"] = "pending"

    @model_validator(mode="after")
    def valid_window(self):
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("Delivery window start and end must be supplied together")
        if self.window_start is not None:
            if self.window_start.utcoffset() is None or self.window_end.utcoffset() is None:
                raise ValueError("Delivery windows must include a timezone")
            if self.window_end <= self.window_start:
                raise ValueError("Delivery window end must follow its start")
        return self


class Vehicle(Coordinates):
    registration: str = Field(min_length=1, max_length=80)
    driver_name: str = Field(min_length=1, max_length=200)
    capacity_kg: float = Field(gt=0, le=100000, allow_inf_nan=False)
    available: bool = True


class DeliveryUpdate(Delivery):
    version: int = Field(ge=1)


class VehicleUpdate(Vehicle):
    version: int = Field(ge=1)


@router.get("/me")
def me(user: dict = Depends(current_user), db=Depends(database)):
    profile = db.collection("users").document(user["uid"]).get(timeout=10, retry=None)
    workspaces = []
    if profile.exists:
        for org_id in profile.to_dict().get("workspace_ids", []):
            org = db.collection("organizations").document(org_id)
            membership = org.collection("members").document(user["uid"]).get(timeout=10, retry=None)
            workspace = org.get(timeout=10, retry=None)
            if membership.exists and workspace.exists:
                workspaces.append({"id": org_id, "name": workspace.to_dict()["name"], "role": membership.to_dict()["role"]})
    return {"uid": user["uid"], "email": user.get("email"), "workspaces": workspaces}


@router.post("/workspaces")
def bootstrap(body: Workspace, user: dict = Depends(current_user), db=Depends(database)):
    # A stable document key plus a transaction makes concurrent bootstrap idempotent.
    profile = db.collection("users").document(user["uid"])
    org = db.collection("organizations").document("workspace_" + user["uid"])

    @firestore.transactional
    def create(transaction):
        existing = org.get(transaction=transaction, timeout=10, retry=None)
        if existing.exists:
            membership = org.collection("members").document(user["uid"]).get(transaction=transaction, timeout=10, retry=None)
            if not membership.exists or membership.to_dict().get("role") != "owner":
                raise HTTPException(409, "Workspace ownership conflict")
            return {"id": org.id, "name": existing.to_dict()["name"], "role": "owner"}
        now = datetime.now(timezone.utc)
        transaction.create(org, {"name": body.name, "created_at": now, "owner_uid": user["uid"]})
        transaction.create(org.collection("members").document(user["uid"]), {"role": "owner", "created_at": now})
        transaction.set(profile, {"workspace_ids": firestore.ArrayUnion([org.id])}, merge=True)
        return {"id": org.id, "name": body.name, "role": "owner"}

    return create(db.transaction())


def records(org_id, kind, user, db):
    member(org_id, user, db)
    return db.collection("organizations").document(org_id).collection(kind)


def list_records(org_id, kind, user, db, limit, cursor):
    collection = records(org_id, kind, user, db)
    query = collection.order_by("__name__").limit(limit + 1)
    if cursor:
        if "/" in cursor:
            raise HTTPException(422, "Invalid cursor")
        query = query.start_after({"__name__": collection.document(cursor)})
    items = [{**doc.to_dict(), "id": doc.id} for doc in query.stream(timeout=10, retry=None)]
    return {"items": items[:limit], "next_cursor": items[limit - 1]["id"] if len(items) > limit else None}


def create_record(org_id, kind, body, user, db):
    collection = records(org_id, kind, user, db)
    ref = collection.document()
    now = datetime.now(timezone.utc)
    data = {**body.model_dump(), "organization_id": org_id, "version": 1, "created_at": now, "updated_at": now}
    ref.create(data, timeout=10, retry=None)
    return {**data, "id": ref.id}


def mutate_record(org_id, kind, record_id, user, db, version, body=None):
    ref = records(org_id, kind, user, db).document(record_id)

    @firestore.transactional
    def change(transaction):
        snapshot = ref.get(transaction=transaction, timeout=10, retry=None)
        if not snapshot.exists:
            raise HTTPException(404, "Record not found")
        old = snapshot.to_dict()
        if old["version"] != version:
            raise HTTPException(409, "Record changed; refresh before saving")
        if body is None:
            transaction.delete(ref)
            return {"deleted": True, "id": ref.id}
        data = {**body.model_dump(exclude={"version"}), "organization_id": org_id, "version": version + 1,
                "created_at": old["created_at"], "updated_at": datetime.now(timezone.utc)}
        transaction.set(ref, data)
        return {**data, "id": ref.id}

    return change(db.transaction())


@router.get("/organizations/{org_id}/deliveries")
def deliveries(org_id: str, limit: int = Query(50, ge=1, le=100), cursor: str | None = None, user: dict = Depends(current_user), db=Depends(database)):
    return list_records(org_id, "deliveries", user, db, limit, cursor)


@router.get("/organizations/{org_id}/vehicles")
def vehicles(org_id: str, limit: int = Query(50, ge=1, le=100), cursor: str | None = None, user: dict = Depends(current_user), db=Depends(database)):
    return list_records(org_id, "vehicles", user, db, limit, cursor)


@router.post("/organizations/{org_id}/deliveries", status_code=201)
def add_delivery(org_id: str, body: Delivery, user: dict = Depends(current_user), db=Depends(database)):
    return create_record(org_id, "deliveries", body, user, db)


@router.post("/organizations/{org_id}/vehicles", status_code=201)
def add_vehicle(org_id: str, body: Vehicle, user: dict = Depends(current_user), db=Depends(database)):
    return create_record(org_id, "vehicles", body, user, db)


@router.put("/organizations/{org_id}/deliveries/{record_id}")
def update_delivery(org_id: str, record_id: str, body: DeliveryUpdate, user: dict = Depends(current_user), db=Depends(database)):
    return mutate_record(org_id, "deliveries", record_id, user, db, body.version, body)


@router.put("/organizations/{org_id}/vehicles/{record_id}")
def update_vehicle(org_id: str, record_id: str, body: VehicleUpdate, user: dict = Depends(current_user), db=Depends(database)):
    return mutate_record(org_id, "vehicles", record_id, user, db, body.version, body)


@router.delete("/organizations/{org_id}/deliveries/{record_id}")
def delete_delivery(org_id: str, record_id: str, expected_version: int = Query(ge=1), user: dict = Depends(current_user), db=Depends(database)):
    return mutate_record(org_id, "deliveries", record_id, user, db, expected_version)


@router.delete("/organizations/{org_id}/vehicles/{record_id}")
def delete_vehicle(org_id: str, record_id: str, expected_version: int = Query(ge=1), user: dict = Depends(current_user), db=Depends(database)):
    return mutate_record(org_id, "vehicles", record_id, user, db, expected_version)


