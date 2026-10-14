from collections.abc import Iterator
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.schemas import (
    ChunkReport,
    DeleteResult,
    FileOut,
    FileStats,
    GlobalStats,
    SnapshotOut,
    UploadResult,
    VersionDeleteResult,
)
from app.services.cow import CoWService
from app.storage.r2 import BlockStore

router = APIRouter(prefix="/api/files", tags=["files"])

_store: BlockStore | None = None


def get_store(settings: Settings = Depends(get_settings)) -> BlockStore:
    global _store
    if _store is None:
        _store = BlockStore(settings)
    return _store


def get_cow(
    db: Session = Depends(get_db),
    store: BlockStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> CoWService:
    return CoWService(db, store, settings)


@router.post("/upload", response_model=UploadResult)
async def upload_file(
    file: UploadFile = File(...),
    file_id: str | None = Form(default=None),
    cow: CoWService = Depends(get_cow),
) -> UploadResult:
    data = await file.read()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    try:
        return cow.upload(file.filename, data, file_id=file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[FileOut])
def list_files(cow: CoWService = Depends(get_cow)) -> list[FileOut]:
    rows = cow.list_files()
    result: list[FileOut] = []
    for row in rows:
        snaps = [
            SnapshotOut.model_validate(s)
            for s in sorted(row.snapshots, key=lambda s: s.version_number)
        ]
        latest = snaps[-1] if snaps else None
        result.append(
            FileOut(
                id=row.id,
                name=row.name,
                created_at=row.created_at,
                snapshots=snaps,
                latest_version=latest.version_number if latest else None,
                latest_size_bytes=latest.file_size_bytes if latest else None,
            )
        )
    return result


@router.get("/stats/global", response_model=GlobalStats)
def global_stats(cow: CoWService = Depends(get_cow)) -> GlobalStats:
    return cow.global_stats()


@router.get("/{file_id}/chunks", response_model=ChunkReport)
def chunk_report(
    file_id: str,
    version: int | None = Query(default=None),
    cow: CoWService = Depends(get_cow),
) -> ChunkReport:
    try:
        return cow.chunk_report(file_id, version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{file_id}/stats", response_model=FileStats)
def file_stats(file_id: str, cow: CoWService = Depends(get_cow)) -> FileStats:
    try:
        return cow.file_stats(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{file_id}")
def get_file(file_id: str, cow: CoWService = Depends(get_cow)) -> FileOut:
    row = cow.get_file(file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    snaps = [
        SnapshotOut.model_validate(s)
        for s in sorted(row.snapshots, key=lambda s: s.version_number)
    ]
    latest = snaps[-1] if snaps else None
    return FileOut(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        snapshots=snaps,
        latest_version=latest.version_number if latest else None,
        latest_size_bytes=latest.file_size_bytes if latest else None,
    )


@router.delete("/{file_id}/versions/{version}", response_model=VersionDeleteResult)
def delete_version(
    file_id: str, version: int, cow: CoWService = Depends(get_cow)
) -> VersionDeleteResult:
    try:
        return cow.delete_version(file_id, version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{file_id}", response_model=DeleteResult)
def delete_file(file_id: str, cow: CoWService = Depends(get_cow)) -> DeleteResult:
    try:
        return cow.delete_file(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    version: int | None = Query(default=None),
    cow: CoWService = Depends(get_cow),
) -> StreamingResponse:
    file_row = cow.get_file(file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")

    snapshot = cow.resolve_snapshot(file_id, version)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    def stream() -> Iterator[bytes]:
        yield from cow.iter_snapshot_blocks(snapshot.id)

    filename = file_row.name
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return StreamingResponse(
        stream(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": disposition,
            "Content-Length": str(snapshot.file_size_bytes),
            "X-Snapshot-Version": str(snapshot.version_number),
            "X-Snapshot-Id": snapshot.id,
        },
    )
