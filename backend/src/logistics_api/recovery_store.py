"""Small transactional store: real Firestore or persistent, labelled SQLite demo."""

import copy
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from google.cloud import firestore

COLLECTIONS = (
    "vehicles", "shipments", "incidents", "recovery_runs", "recovery_feedback",
    "policy_settings", "audit_logs",
)


class LocalStore:
    mode = "local_demo"
    notice = "Local demo: changes are saved to SQLite on this machine, NOT to Firestore."

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id))")

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def mutate(self, operation):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            state = {kind: {} for kind in COLLECTIONS}
            for kind, key, body in db.execute("SELECT kind,id,body FROM documents"):
                state[kind][key] = json.loads(body)
            before = copy.deepcopy(state)
            result = operation(state)
            for kind in COLLECTIONS:
                for key in before[kind].keys() - state[kind].keys():
                    db.execute("DELETE FROM documents WHERE kind=? AND id=?", (kind, key))
                for key, value in state[kind].items():
                    if before[kind].get(key) != value:
                        db.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?)", (kind, key, json.dumps(value)))
            return copy.deepcopy(result)

    def snapshot(self):
        return self.mutate(lambda state: state)


class FirestoreStore:
    mode = "firestore"
    notice = "Changes are persisted to Firebase Cloud Firestore."

    def __init__(self, client, workspace_id: str, emulator=False):
        self.client = client
        self.root = client.collection("organizations").document(workspace_id)
        self.emulator = emulator
        if emulator:
            self.notice = "Firestore emulator: changes are NOT written to cloud Firestore."

    def mutate(self, operation):
        @firestore.transactional
        def apply(transaction):
            # All recovery writers touch this guard, including inserts, so a fleet
            # change cannot slip between the collection reads and assignment writes.
            guard = self.root.collection("policy_settings").document("recovery_lock")
            lock = guard.get(transaction=transaction, timeout=10)
            state = {kind: {} for kind in COLLECTIONS}
            for kind in COLLECTIONS:
                for doc in self.root.collection(kind).stream(transaction=transaction, timeout=10):
                    if kind == "policy_settings" and doc.id == "recovery_lock":
                        continue
                    state[kind][doc.id] = doc.to_dict()
            before = copy.deepcopy(state)
            result = operation(state)
            changes = []
            for kind in COLLECTIONS:
                for key in before[kind].keys() - state[kind].keys():
                    changes.append((self.root.collection(kind).document(key), None))
                for key, value in state[kind].items():
                    if before[kind].get(key) != value:
                        changes.append((self.root.collection(kind).document(key), value))
            if len(changes) > 450:
                raise RuntimeError("MVP transaction limit exceeded; reduce workspace demo data.")
            if changes:
                transaction.set(guard, {"version": (lock.to_dict() or {}).get("version", 0) + 1})
                for ref, value in changes:
                    if value is None:
                        transaction.delete(ref)
                    else:
                        transaction.set(ref, value)
            return copy.deepcopy(result)

        return apply(self.client.transaction(max_attempts=5))

    def snapshot(self):
        return self.mutate(lambda state: state)
