import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.models import Block, File, Snapshot, SnapshotBlock
from app.schemas import (
    ChunkReport,
    ChunkSlot,
    DeleteResult,
    FileStats,
    GlobalStats,
    UploadResult,
    VersionChunks,
    VersionDeleteResult,
)
from app.storage.chunker import chunk_bytes
from app.storage.r2 import BlockStore


class CoWService:
    """Copy-on-Write deduplication engine over Neon + R2."""

    def __init__(self, db: Session, store: BlockStore, settings: Settings):
        self.db = db
        self.store = store
        self.settings = settings

    def upload(
        self,
        filename: str,
        data: bytes,
        file_id: str | None = None,
    ) -> UploadResult:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if file_id:
            file_row = self.db.get(File, file_id)
            if file_row is None:
                raise ValueError(f"File not found: {file_id}")
            next_version = (
                self.db.scalar(
                    select(func.coalesce(func.max(Snapshot.version_number), 0)).where(
                        Snapshot.file_id == file_id
                    )
                )
                or 0
            ) + 1
        else:
            file_id = str(uuid.uuid4())
            file_row = File(id=file_id, name=filename, created_at=now)
            self.db.add(file_row)
            next_version = 1

        snapshot_id = str(uuid.uuid4())
        snapshot = Snapshot(
            id=snapshot_id,
            file_id=file_id,
            version_number=next_version,
            snapshot_time=now,
            file_size_bytes=len(data),
        )
        self.db.add(snapshot)

        new_chunks = 0
        reused_chunks = 0
        bytes_uploaded = 0
        bytes_deduplicated = 0
        total_chunks = 0
        pending: dict[str, Block] = {}

        for block_index, block_hash, chunk in chunk_bytes(
            data, self.settings.chunk_size_bytes
        ):
            total_chunks += 1
            existing = pending.get(block_hash)
            if existing is None:
                existing = self.db.get(Block, block_hash)

            if existing is not None:
                existing.ref_count += 1
                reused_chunks += 1
                bytes_deduplicated += len(chunk)
            else:
                storage_path = self.store.put(block_hash, chunk)
                existing = Block(
                    hash=block_hash,
                    storage_path=storage_path,
                    size_bytes=len(chunk),
                    ref_count=1,
                )
                self.db.add(existing)
                new_chunks += 1
                bytes_uploaded += len(chunk)

            pending[block_hash] = existing
            self.db.add(
                SnapshotBlock(
                    snapshot_id=snapshot_id,
                    block_index=block_index,
                    block_hash=block_hash,
                )
            )

        self.db.commit()

        return UploadResult(
            file_id=file_id,
            name=file_row.name,
            snapshot_id=snapshot_id,
            version_number=next_version,
            file_size_bytes=len(data),
            total_chunks=total_chunks,
            new_chunks=new_chunks,
            reused_chunks=reused_chunks,
            bytes_uploaded=bytes_uploaded,
            bytes_deduplicated=bytes_deduplicated,
        )

    def list_files(self) -> list[File]:
        return list(
            self.db.scalars(
                select(File)
                .options(joinedload(File.snapshots))
                .order_by(File.created_at.desc())
            ).unique()
        )

    def get_file(self, file_id: str) -> File | None:
        return self.db.scalars(
            select(File)
            .where(File.id == file_id)
            .options(joinedload(File.snapshots))
        ).first()

    def resolve_snapshot(
        self, file_id: str, version: int | None
    ) -> Snapshot | None:
        query = select(Snapshot).where(Snapshot.file_id == file_id)
        if version is not None:
            query = query.where(Snapshot.version_number == version)
        else:
            query = query.order_by(Snapshot.version_number.desc()).limit(1)
        return self.db.scalars(query).first()

    def chunk_report(self, file_id: str, version: int | None) -> ChunkReport:
        file_row = self.get_file(file_id)
        if file_row is None:
            raise ValueError(f"File not found: {file_id}")
        current = self.resolve_snapshot(file_id, version)
        if current is None:
            raise ValueError("Snapshot not found")

        snap_ids = [s.id for s in file_row.snapshots]
        links = self.db.execute(
            select(
                Snapshot.id,
                Snapshot.version_number,
                Snapshot.snapshot_time,
                SnapshotBlock.block_index,
                SnapshotBlock.block_hash,
                Block.size_bytes,
            )
            .join(SnapshotBlock, SnapshotBlock.snapshot_id == Snapshot.id)
            .join(Block, Block.hash == SnapshotBlock.block_hash)
            .where(Snapshot.id.in_(snap_ids))
            .order_by(Snapshot.version_number, SnapshotBlock.block_index)
        ).all()

        hashes = {row.block_hash for row in links}
        origin: dict[str, tuple] = {}
        if hashes:
            seen = self.db.execute(
                select(
                    SnapshotBlock.block_hash,
                    Snapshot.id,
                    Snapshot.snapshot_time,
                    SnapshotBlock.block_index,
                )
                .join(Snapshot, Snapshot.id == SnapshotBlock.snapshot_id)
                .where(SnapshotBlock.block_hash.in_(hashes))
            ).all()
            for block_hash, snap_id, snap_time, block_index in seen:
                key = (snap_time, snap_id, block_index)
                previous = origin.get(block_hash)
                if previous is None or key < previous:
                    origin[block_hash] = key

        grouped: dict[str, list] = {}
        for row in links:
            grouped.setdefault(row.id, []).append(row)

        def summarize(rows: list) -> tuple[VersionChunks, list[ChunkSlot]]:
            slots: list[ChunkSlot] = []
            new_count = 0
            for row in rows:
                born = origin[row.block_hash]
                is_new = born[1] == row.id and born[2] == row.block_index
                if is_new:
                    new_count += 1
                slots.append(
                    ChunkSlot(
                        index=row.block_index,
                        status="new" if is_new else "reused",
                        hash_prefix=row.block_hash[:8],
                        size_bytes=row.size_bytes,
                    )
                )
            summary = VersionChunks(
                version_number=rows[0].version_number if rows else 0,
                chunk_count=len(rows),
                unique_count=len({row.block_hash for row in rows}),
                new_count=new_count,
                reused_count=len(rows) - new_count,
            )
            return summary, slots

        versions: list[VersionChunks] = []
        selected_slots: list[ChunkSlot] = []
        selected_summary = VersionChunks(
            version_number=current.version_number,
            chunk_count=0,
            unique_count=0,
            new_count=0,
            reused_count=0,
        )
        for snap in sorted(file_row.snapshots, key=lambda s: s.version_number):
            summary, slots = summarize(grouped.get(snap.id, []))
            summary.version_number = snap.version_number
            versions.append(summary)
            if snap.id == current.id:
                selected_summary = summary
                selected_slots = slots

        return ChunkReport(
            file_id=file_id,
            version_number=current.version_number,
            chunk_count=selected_summary.chunk_count,
            unique_count=selected_summary.unique_count,
            new_count=selected_summary.new_count,
            reused_count=selected_summary.reused_count,
            slots=selected_slots[:64],
            versions=versions,
        )

    def iter_snapshot_blocks(self, snapshot_id: str) -> Iterator[bytes]:
        rows = self.db.scalars(
            select(SnapshotBlock)
            .where(SnapshotBlock.snapshot_id == snapshot_id)
            .order_by(SnapshotBlock.block_index)
        ).all()
        for row in rows:
            yield self.store.get(row.block_hash)

    def _release(self, usage: list[tuple[str, int]]) -> tuple[int, int, int]:
        """Drop ref_count for hashes whose snapshot rows are already gone."""
        released = 0
        kept = 0
        reclaimed = 0
        orphans: list[str] = []
        for block_hash, count in usage:
            block = self.db.get(Block, block_hash)
            if block is None:
                continue
            block.ref_count -= int(count)
            if block.ref_count <= 0:
                reclaimed += block.size_bytes
                released += 1
                orphans.append(block_hash)
                self.db.delete(block)
            else:
                kept += 1
        self.db.commit()
        for block_hash in orphans:
            self.store.delete(block_hash)
        return released, kept, reclaimed

    def delete_version(self, file_id: str, version: int) -> VersionDeleteResult:
        file_row = self.db.get(File, file_id)
        if file_row is None:
            raise ValueError(f"File not found: {file_id}")
        snapshot = self.resolve_snapshot(file_id, version)
        if snapshot is None:
            raise ValueError(f"Version not found: {version}")

        usage = self.db.execute(
            select(SnapshotBlock.block_hash, func.count())
            .where(SnapshotBlock.snapshot_id == snapshot.id)
            .group_by(SnapshotBlock.block_hash)
        ).all()
        name = file_row.name
        others = (
            self.db.scalar(
                select(func.count())
                .select_from(Snapshot)
                .where(Snapshot.file_id == file_id, Snapshot.id != snapshot.id)
            )
            or 0
        )
        file_removed = others == 0
        if file_removed:
            self.db.delete(file_row)
        else:
            self.db.delete(snapshot)
        self.db.flush()

        released, kept, reclaimed = self._release(list(usage))
        return VersionDeleteResult(
            file_id=file_id,
            name=name,
            version_number=version,
            file_removed=file_removed,
            blocks_released=released,
            blocks_kept_shared=kept,
            bytes_reclaimed=reclaimed,
        )

    def delete_file(self, file_id: str) -> DeleteResult:
        file_row = self.db.get(File, file_id)
        if file_row is None:
            raise ValueError(f"File not found: {file_id}")

        version_count = (
            self.db.scalar(
                select(func.count())
                .select_from(Snapshot)
                .where(Snapshot.file_id == file_id)
            )
            or 0
        )
        usage = self.db.execute(
            select(SnapshotBlock.block_hash, func.count())
            .join(Snapshot, Snapshot.id == SnapshotBlock.snapshot_id)
            .where(Snapshot.file_id == file_id)
            .group_by(SnapshotBlock.block_hash)
        ).all()

        name = file_row.name
        self.db.delete(file_row)
        self.db.flush()
        released, kept, reclaimed = self._release(list(usage))

        return DeleteResult(
            file_id=file_id,
            name=name,
            versions_removed=int(version_count),
            blocks_released=released,
            blocks_kept_shared=kept,
            bytes_reclaimed=reclaimed,
        )

    def file_stats(self, file_id: str) -> FileStats:
        file_row = self.get_file(file_id)
        if file_row is None:
            raise ValueError(f"File not found: {file_id}")

        snapshots = file_row.snapshots
        logical_bytes = sum(s.file_size_bytes for s in snapshots)

        unique_block_rows = self.db.execute(
            select(Block.hash, Block.size_bytes)
            .join(SnapshotBlock, SnapshotBlock.block_hash == Block.hash)
            .join(Snapshot, Snapshot.id == SnapshotBlock.snapshot_id)
            .where(Snapshot.file_id == file_id)
            .distinct()
        ).all()

        physical_bytes = sum(size for _, size in unique_block_rows)
        ref_count = self.db.scalar(
            select(func.count())
            .select_from(SnapshotBlock)
            .join(Snapshot, Snapshot.id == SnapshotBlock.snapshot_id)
            .where(Snapshot.file_id == file_id)
        ) or 0

        saved = max(logical_bytes - physical_bytes, 0)
        pct = (saved / logical_bytes * 100.0) if logical_bytes else 0.0

        return FileStats(
            file_id=file_id,
            name=file_row.name,
            version_count=len(snapshots),
            logical_bytes=logical_bytes,
            physical_bytes=physical_bytes,
            bytes_saved=saved,
            savings_percent=round(pct, 2),
            unique_blocks=len(unique_block_rows),
            total_block_references=ref_count,
        )

    def global_stats(self) -> GlobalStats:
        file_count = self.db.scalar(select(func.count()).select_from(File)) or 0
        snapshot_count = (
            self.db.scalar(select(func.count()).select_from(Snapshot)) or 0
        )
        unique_blocks = self.db.scalar(select(func.count()).select_from(Block)) or 0
        logical_bytes = int(
            self.db.scalar(select(func.coalesce(func.sum(Snapshot.file_size_bytes), 0)))
            or 0
        )
        physical_bytes = int(
            self.db.scalar(select(func.coalesce(func.sum(Block.size_bytes), 0))) or 0
        )
        saved = max(logical_bytes - physical_bytes, 0)
        pct = (saved / logical_bytes * 100.0) if logical_bytes else 0.0

        return GlobalStats(
            file_count=file_count,
            snapshot_count=snapshot_count,
            unique_blocks=unique_blocks,
            logical_bytes=int(logical_bytes),
            physical_bytes=int(physical_bytes),
            bytes_saved=saved,
            savings_percent=round(pct, 2),
        )
