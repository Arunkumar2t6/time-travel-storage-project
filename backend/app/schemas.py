from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    snapshot_time: datetime
    file_size_bytes: int


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
    snapshots: list[SnapshotOut] = []
    latest_version: int | None = None
    latest_size_bytes: int | None = None


class UploadResult(BaseModel):
    file_id: str
    name: str
    snapshot_id: str
    version_number: int
    file_size_bytes: int
    total_chunks: int
    new_chunks: int
    reused_chunks: int
    bytes_uploaded: int
    bytes_deduplicated: int


class DeleteResult(BaseModel):
    file_id: str
    name: str
    versions_removed: int
    blocks_released: int
    blocks_kept_shared: int
    bytes_reclaimed: int


class VersionDeleteResult(BaseModel):
    file_id: str
    name: str
    version_number: int
    file_removed: bool
    blocks_released: int
    blocks_kept_shared: int
    bytes_reclaimed: int


class FileStats(BaseModel):
    file_id: str
    name: str
    version_count: int
    logical_bytes: int
    physical_bytes: int
    bytes_saved: int
    savings_percent: float
    unique_blocks: int
    total_block_references: int


class ChunkSlot(BaseModel):
    index: int
    status: str
    hash_prefix: str
    size_bytes: int


class VersionChunks(BaseModel):
    version_number: int
    chunk_count: int
    unique_count: int
    new_count: int
    reused_count: int


class ChunkReport(BaseModel):
    file_id: str
    version_number: int
    chunk_count: int
    unique_count: int
    new_count: int
    reused_count: int
    slots: list[ChunkSlot]
    versions: list[VersionChunks]


class GlobalStats(BaseModel):
    file_count: int
    snapshot_count: int
    unique_blocks: int
    logical_bytes: int
    physical_bytes: int
    bytes_saved: int
    savings_percent: float
