from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    snapshots: Mapped[list["Snapshot"]] = relationship(
        "Snapshot",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="Snapshot.version_number",
    )


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        UniqueConstraint("file_id", "version_number", name="uq_file_version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    file_id: Mapped[str] = mapped_column(
        String, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    file: Mapped["File"] = relationship("File", back_populates="snapshots")
    blocks: Mapped[list["SnapshotBlock"]] = relationship(
        "SnapshotBlock",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="SnapshotBlock.block_index",
    )


class Block(Base):
    __tablename__ = "blocks"

    hash: Mapped[str] = mapped_column(String, primary_key=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    snapshot_links: Mapped[list["SnapshotBlock"]] = relationship(
        "SnapshotBlock", back_populates="block"
    )


class SnapshotBlock(Base):
    __tablename__ = "snapshot_blocks"

    snapshot_id: Mapped[str] = mapped_column(
        String, ForeignKey("snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    block_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_hash: Mapped[str] = mapped_column(
        String, ForeignKey("blocks.hash"), nullable=False
    )

    snapshot: Mapped["Snapshot"] = relationship("Snapshot", back_populates="blocks")
    block: Mapped["Block"] = relationship("Block", back_populates="snapshot_links")
