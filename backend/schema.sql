-- Time-Travel CoW Vault — Neon PostgreSQL schema

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    snapshot_time TIMESTAMP NOT NULL DEFAULT NOW(),
    file_size_bytes BIGINT NOT NULL DEFAULT 0,
    UNIQUE (file_id, version_number)
);

CREATE TABLE IF NOT EXISTS blocks (
    hash TEXT PRIMARY KEY,
    storage_path TEXT NOT NULL,
    size_bytes INT NOT NULL,
    ref_count INT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS snapshot_blocks (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    block_index INT NOT NULL,
    block_hash TEXT NOT NULL REFERENCES blocks(hash),
    PRIMARY KEY (snapshot_id, block_index)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_file_id ON snapshots(file_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_blocks_hash ON snapshot_blocks(block_hash);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at DESC);
