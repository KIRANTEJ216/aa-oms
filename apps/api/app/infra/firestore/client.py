import os

# Lazy import so emulator can run without real credentials
_db = None
_emulator_warned = False


def _is_production() -> bool:
    vercel = os.getenv("VERCEL", "")
    env = os.getenv("APP_ENV", os.getenv("ENV", "development")).lower()
    return bool(vercel) or env in ("production", "prod")


def get_db():
    global _db, _emulator_warned
    if _db is not None:
        return _db
    emulator = os.getenv("FIRESTORE_EMULATOR_HOST")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "caoms-dev")
    try:
        from google.cloud import firestore
        if emulator:
            # Emulator: no credentials needed, bypass auth
            # Create anonymous credentials for emulator
            # Use firestore.Client with emulator host — it ignores credentials
            _db = firestore.Client(project=project)
            # Point to emulator via env var already set
        else:
            from firebase_admin import firestore as fa_firestore

            from app.infra.firebase.client import get_firebase_app

            app = get_firebase_app()
            if app is None:
                # Production must not silently degrade to an in-memory stub —
                # two serverless instances would hold different data.
                raise RuntimeError(
                    "Firestore not configured: set FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL "
                    "and FIREBASE_PRIVATE_KEY (or FIRESTORE_EMULATOR_HOST for local dev)"
                )
            _db = fa_firestore.client(app=app)
    except Exception as e:
        if isinstance(e, RuntimeError) and str(e).startswith("Firestore not configured") and _is_production():
            raise
        # Fallback: in-memory stub for local dev without emulator
        if not _emulator_warned:
            print(f"[firestore] using in-memory stub (emulator not reachable): {e}")
            _emulator_warned = True
        _db = _InMemoryFirestore()
    return _db

# ── In-memory stub (dev without emulator) ────────────────────────
class _InMemoryDoc:
    def __init__(self, store, col, doc_id): self.store=store; self.col=col; self.doc_id=doc_id
    def get(self):
        data = self.store.get((self.col, self.doc_id))
        return _Snap(data is not None, data or {}, self.doc_id)
    def set(self, data, merge=False):
        existing = self.store.get((self.col, self.doc_id), {})
        self.store[(self.col, self.doc_id)] = {**existing, **data} if merge else data
        _save_store(self.store)
    def update(self, data):
        existing = self.store.get((self.col, self.doc_id), {})
        existing.update(data)
        self.store[(self.col, self.doc_id)] = existing
    def delete(self): self.store.pop((self.col, self.doc_id), None); _save_store(self.store)
    def collection(self, sub): return _InMemoryCollection(self.store, f"{self.col}/{self.doc_id}/{sub}")

class _Snap:
    def __init__(self, exists, data, doc_id="stub-id"): self.exists=exists; self._data=data; self._id=doc_id
    def to_dict(self): return self._data
    @property
    def id(self): return self._id

class _InMemoryCollection:
    def __init__(self, store, name): self.store=store; self.name=name
    def document(self, doc_id=None):
        import uuid
        if not doc_id: doc_id=str(uuid.uuid4())
        return _InMemoryDoc(self.store, self.name, doc_id)
    def where(self, field, op, value): return _InMemoryQuery(self.store, self.name, [(field, op, value)])
    def order_by(self, field, direction="ASCENDING"): return _InMemoryQuery(self.store, self.name, [], order=(field, direction))
    def limit(self, n): return _InMemoryQuery(self.store, self.name, [], limit=n)
    def stream(self): return [ _Snap(True, v, doc_id) for (c,doc_id), v in self.store.items() if c==self.name ]
    def get(self): return list(self.stream())

class _InMemoryQuery:
    def __init__(self, store, name, filters, order=None, limit=None): self.store=store; self.name=name; self.filters=filters; self._order=order; self._limit=limit
    def where(self, f, op, v): return _InMemoryQuery(self.store, self.name, self.filters+[(f,op,v)], self._order, self._limit)
    def order_by(self, f, d="ASCENDING"): return _InMemoryQuery(self.store, self.name, self.filters, (f,d), self._limit)
    def limit(self, n): return _InMemoryQuery(self.store, self.name, self.filters, self._order, n)
    def offset(self, n): return self
    def stream(self):
        out=[]
        for (c,doc_id), v in self.store.items():
            if c!=self.name: continue
            ok=True
            for f,op,val in self.filters:
                if op=="==" and v.get(f)!=val: ok=False
                if op=="!=" and v.get(f)==val: ok=False
            if ok: out.append(_Snap(True, v, doc_id))
        if self._order:
            out.sort(key=lambda s: s.to_dict().get(self._order[0],""))
        if self._limit is not None: out=out[:self._limit]
        return out
    def get(self): return list(self.stream())

_PERSIST_PATH = "/tmp/caoms_firestore.json"

def _load_store():
    try:
        import json as _j
        import os as _o
        if _o.path.exists(_PERSIST_PATH):
            raw = _j.load(open(_PERSIST_PATH))
            # raw is dict with "col|doc_id" keys
            return {tuple(k.split("|",1)): v for k,v in raw.items()}
    except Exception:
        pass
    return {}

def _save_store(store):
    try:
        import json as _j
        raw = {f"{c}|{did}": v for (c,did), v in store.items()}
        _j.dump(raw, open(_PERSIST_PATH, "w"), default=str)
    except Exception:
        pass

class _InMemoryFirestore:
    def __init__(self):
        self.store = _load_store()
    def collection(self, name): return _InMemoryCollection(self.store, name)
    def batch(self): return _InMemoryBatch(self.store)

class _InMemoryBatch:
    def __init__(self, store): self.store=store; self.ops=[]
    def set(self, ref, data): self.ops.append(("set", ref, data))
    def commit(self):
        for op, ref, data in self.ops: ref.set(data)
