from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers.files import router as files_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


settings = get_settings()

app = FastAPI(
    title="Time-Travel CoW Vault",
    description="Copy-on-Write version control for files with KB-level CAS deduplication",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "time-travel-cow-vault",
        "chunk_size_bytes": settings.chunk_size_bytes,
        "storage": "local" if settings.use_local_storage else "neon_object_storage",
    }


@app.get("/health/storage")
def health_storage():
    """Probe Neon Object Storage / local block store (write+delete tiny object)."""
    from app.storage.object_store import BlockStore

    store = BlockStore(settings)
    probe_hash = "0" * 64
    try:
        store.put(probe_hash, b"healthcheck")
        store.delete(probe_hash)
        return {"status": "ok", "storage": "local" if store._local else "neon_object_storage"}
    except Exception as exc:
        return {
            "status": "error",
            "storage": "local" if store._local else "neon_object_storage",
            "detail": f"{type(exc).__name__}: {exc}",
        }
