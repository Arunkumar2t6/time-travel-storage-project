import { useRef, useState } from "react";

export default function UploadZone({ onUpload, busy }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");

  async function handleFiles(fileList) {
    const file = fileList?.[0];
    if (!file) return;
    setError("");
    setProgress(0);
    try {
      await onUpload(file, null, setProgress);
      setProgress(null);
    } catch (err) {
      setError(err.message || "Upload failed");
      setProgress(null);
    }
  }

  return (
    <div
      className={`vault-panel relative overflow-hidden p-6 transition ${
        dragging ? "border-brass shadow-glow" : ""
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "linear-gradient(var(--color-line) 1px, transparent 1px), linear-gradient(90deg, var(--color-line) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />
      <div className="relative flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-brass">
            Ingest
          </p>
          <h2 className="mt-1 font-display text-2xl font-bold tracking-tight text-paper sm:text-3xl">
            Drop file into vault
          </h2>
          <p className="mt-2 max-w-md text-sm text-paper/65">
            Each drop is a new file. Matching 256 KB chunks are shared in
            storage and still listed as separate files.
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
          <button
            type="button"
            className="vault-btn"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {busy ? "Chunking…" : "New file"}
          </button>
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              handleFiles(e.target.files);
              e.target.value = "";
            }}
          />
          {progress != null && (
            <div className="w-44">
              <div className="h-1 w-full bg-line">
                <div
                  className="h-1 bg-brass transition-all duration-150"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="mt-1 font-mono text-[11px] text-paper/50">
                {progress}%
              </p>
            </div>
          )}
          {error && (
            <p className="max-w-xs text-right text-xs text-danger" role="alert">
              {error}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
