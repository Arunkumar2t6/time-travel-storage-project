import { useCallback, useEffect, useMemo, useState } from "react";
import {
  deleteFile,
  deleteVersion,
  getChunkReport,
  getGlobalStats,
  listFiles,
  uploadFile,
} from "./api";
import FileManager from "./components/FileManager";
import StorageStats from "./components/StorageStats";
import TimeTravel from "./components/TimeTravel";
import UploadZone from "./components/UploadZone";

/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 */

export default function App() {
  const [files, setFiles] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [version, setVersion] = useState(null);
  const [globalStats, setGlobalStats] = useState(null);
  const [chunks, setChunks] = useState(null);
  const [busy, setBusy] = useState(false);
  const [lastUpload, setLastUpload] = useState(null);
  const [error, setError] = useState("");

  const selected = useMemo(
    () => files.find((f) => f.id === selectedId) || null,
    [files, selectedId]
  );

  const refresh = useCallback(async () => {
    try {
      const [fileList, gStats] = await Promise.all([
        listFiles(),
        getGlobalStats(),
      ]);
      setFiles(fileList);
      setGlobalStats(gStats);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load vault");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!selected) {
      setVersion(null);
      setChunks(null);
      return;
    }
    const latest =
      selected.latest_version ??
      selected.snapshots?.[selected.snapshots.length - 1]?.version_number;
    setVersion(latest ?? null);
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedId || version == null) return;
    getChunkReport(selectedId, version)
      .then(setChunks)
      .catch(() => setChunks(null));
  }, [selectedId, version, files]);

  async function handleDelete(file) {
    const ok = window.confirm(
      `Delete ${file.name} and every version? Shared blocks stay if another file still uses them.`
    );
    if (!ok) return;
    setBusy(true);
    setError("");
    try {
      await deleteFile(file.id);
      if (selectedId === file.id) setSelectedId(null);
      setLastUpload(null);
      await refresh();
    } catch (err) {
      setError(err.message || "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteVersion(file, versionNumber) {
    const lastOne = (file.snapshots?.length || 0) <= 1;
    const ok = window.confirm(
      lastOne
        ? `Delete v${versionNumber}? It is the only version, so ${file.name} leaves the vault. Shared blocks stay if another file still uses them.`
        : `Delete v${versionNumber} of ${file.name}? Shared blocks stay if another version or file still uses them.`
    );
    if (!ok) return;
    setBusy(true);
    setError("");
    try {
      const result = await deleteVersion(file.id, versionNumber);
      if (result.file_removed) setSelectedId(null);
      setLastUpload(null);
      await refresh();
    } catch (err) {
      setError(err.message || "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(file, fileId, onProgress) {
    setBusy(true);
    try {
      const result = await uploadFile(file, fileId, onProgress);
      setLastUpload(result);
      await refresh();
      setSelectedId(result.file_id);
      setVersion(result.version_number);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto min-h-screen max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <header className="animate-rise mb-8">
        <p className="font-mono text-xs uppercase tracking-[0.28em] text-brass">
          CoW Vault
        </p>
        <h1
          className="mt-2 font-display text-4xl font-extrabold tracking-tight text-paper sm:text-5xl md:text-6xl"
          style={{ overflowWrap: "anywhere" }}
        >
          Time-Travel
        </h1>
        <p className="mt-3 max-w-xl text-sm text-paper/60 sm:text-base">
          Content-addressed KB chunks. Immutable snapshots. Scrub any past
          version — physical blocks shared across history.
        </p>
      </header>

      {error && (
        <div
          className="mb-6 border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="space-y-6">
        <UploadZone onUpload={handleUpload} busy={busy} />

        <StorageStats globalStats={globalStats} />

        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <FileManager
              files={files}
              selectedId={selectedId}
              lastUpload={lastUpload}
              onSelect={(id) => setSelectedId(id)}
              onDelete={handleDelete}
              onVersion={async (existing, file) => {
                try {
                  await handleUpload(file, existing.id);
                } catch (err) {
                  setError(err.message || "Upload failed");
                }
              }}
              busy={busy}
            />
          </div>
          <div className="lg:col-span-3">
            <TimeTravel
              file={selected}
              version={version}
              busy={busy}
              onVersionChange={setVersion}
              onDeleteVersion={handleDeleteVersion}
              onDelete={handleDelete}
              onVersion={async (existing, picked) => {
                try {
                  await handleUpload(picked, existing.id);
                } catch (err) {
                  setError(err.message || "Upload failed");
                }
              }}
              chunks={chunks}
            />
          </div>
        </div>
      </div>

      <footer className="mt-12 border-t border-line pt-6 font-mono text-[11px] text-paper/35">
        Neon · Cloudflare R2 · FastAPI · 256 KB CAS blocks
      </footer>
    </div>
  );
}
