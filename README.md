# Time-Travel CoW Vault

Enterprise Copy-on-Write version control for files. Uploads are split into content-addressed KB chunks (default **256 KB**), deduplicated against Neon PostgreSQL, and stored in **Neon Object Storage** (S3-compatible). Every upload creates an immutable snapshot; any past version can be reconstructed on the fly.

## Architecture

```
React (Vercel) ──► FastAPI (Render) ──► Neon PostgreSQL (metadata)
                              └──► Neon Object Storage (CAS blocks via boto3)
```

1. **Chunk** file into SHA-256 hashed blocks
2. **Lookup** hash in `blocks` table
3. **Reuse** existing block (`ref_count++`) or **upload** new bytes to Neon Object Storage
4. **Snapshot** maps ordered `snapshot_blocks` for reconstruction

## Directory structure

```
time-travel/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry
│   │   ├── config.py            # Neon Postgres + Object Storage settings
│   │   ├── database.py          # SQLAlchemy engine
│   │   ├── models.py            # ORM (files, snapshots, blocks, snapshot_blocks)
│   │   ├── schemas.py           # Pydantic DTOs
│   │   ├── routers/files.py     # REST API
│   │   ├── services/cow.py      # CoW dedup engine
│   │   └── storage/
│   │       ├── chunker.py       # KB chunking + SHA-256
│   │       └── object_store.py  # Neon Object Storage / local store
│   ├── schema.sql
│   ├── requirements.txt
│   ├── Dockerfile
│   └── render.yaml
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   └── components/
│   │       ├── UploadZone.jsx
│   │       ├── FileManager.jsx
│   │       ├── TimeTravel.jsx
│   │       └── StorageStats.jsx
│   ├── vercel.json
│   └── package.json
└── docker-compose.yml
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/files/upload` | Ingest file (optional `file_id` form field for new version) |
| `GET` | `/api/files` | List files + version trees |
| `GET` | `/api/files/{file_id}` | Single file detail |
| `GET` | `/api/files/{file_id}/download?version=X` | Reconstruct & stream version |
| `GET` | `/api/files/{file_id}/stats` | Per-file storage savings |
| `GET` | `/api/files/stats/global` | Vault-wide savings |
| `GET` | `/health` | Health check |

## Local development

### Backend (with local disk instead of Neon Object Storage)

Requires **Python 3.11–3.12** (Docker image uses 3.12).

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set DATABASE_URL to Neon (or use docker-compose db)
# USE_LOCAL_STORAGE=true for local block store
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # leave VITE_API_URL empty to use Vite proxy
npm run dev
```

### Docker Compose (API + Postgres, local blocks)

```bash
docker compose up --build
```

## Production deploy

### Neon (Postgres + Object Storage)

1. Create a Neon project in a supported region (`aws-us-east-2`, `aws-us-east-1`, `aws-eu-central-1`, or `aws-ap-southeast-1`)
2. Copy the Postgres connection string → `DATABASE_URL`
3. Enable Object Storage (Console → Object storage, or `neon deploy` with a `buckets` entry)
4. Create bucket `time-travel-blocks` (private)
5. Create credential with `storage:read` + `storage:write`:
   ```bash
   neon credentials create --scope storage:read --scope storage:write
   ```
6. Set env from credential + branch storage endpoint:
   - `AWS_ACCESS_KEY_ID` = `token_id` (`nak_live_...`)
   - `AWS_SECRET_ACCESS_KEY` = `s3_secret_access_key` (`nsk_live_...`)
   - `AWS_ENDPOINT_URL_S3` = branch `s3_endpoint` (e.g. `https://br-….storage.c-2.us-east-2.aws.neon.tech`)
   - `AWS_REGION` = e.g. `us-east-2`
   - `S3_BUCKET_NAME` = `time-travel-blocks`
7. Tables auto-create on API startup via SQLAlchemy (`schema.sql` is also available)

Free plan includes **5 GB** object storage per project. No Cloudflare card needed.

### Render (backend)

1. New Web Service from `backend/` with Docker
2. Set env vars from `backend/.env.example`
3. Health check: `/health`

### Vercel (frontend)

1. Import `frontend/` as the project root
2. Set `VITE_API_URL` to your Render URL
3. Build: `npm run build` · Output: `dist`

## Env reference

**Backend**

- `DATABASE_URL` — Neon Postgres URL
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — Neon storage credential
- `AWS_ENDPOINT_URL_S3` / `AWS_REGION` / `S3_BUCKET_NAME` — Neon Object Storage
- `CHUNK_SIZE_BYTES` — default `262144` (256 KB)
- `CORS_ORIGINS` — comma-separated frontend origins
- `USE_LOCAL_STORAGE` — `true` skips object storage (dev)

**Frontend**

- `VITE_API_URL` — backend base URL (no trailing slash)

## Storage savings math

- **Logical bytes** = sum of all snapshot `file_size_bytes`
- **Physical bytes** = sum of unique `blocks.size_bytes` referenced by those snapshots
- **Saved** = logical − physical (KB-level CoW sharing across versions)
