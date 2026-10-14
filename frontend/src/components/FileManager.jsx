import { useRef } from "react";
import { formatBytes, formatTime } from "../api";
import { TrashButton, VersionButton } from "./ActionIcons";

export default function FileManager({
  files,
  selectedId,
  onSelect,
  onDelete,
  onVersion,
  busy,
  lastUpload,
}) {
  const inputRef = useRef(null);
  const targetRef = useRef(null);

  function startVersion(file) {
    targetRef.current = file;
    inputRef.current?.click();
  }
  return (
    <div className="vault-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <h3 className="font-display text-lg font-bold text-paper">Files</h3>
        <span className="font-mono text-xs text-paper/40">
          {files.length} managed
        </span>
      </div>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={(e) => {
          const picked = e.target.files?.[0];
          const target = targetRef.current;
          e.target.value = "";
          if (picked && target) onVersion(target, picked);
        }}
      />

      {lastUpload && (
        <div className="border-b border-line bg-brass/10 px-5 py-3 font-mono text-[11px] text-brass">
          Snapshot v{lastUpload.version_number} · {lastUpload.new_chunks} new /{" "}
          {lastUpload.reused_chunks} reused · saved{" "}
          {formatBytes(lastUpload.bytes_deduplicated)}
        </div>
      )}

      {files.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-paper/45">
          Vault empty. Upload first file to begin versioning.
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {files.map((f) => {
            const active = f.id === selectedId;
            return (
              <li
                key={f.id}
                className={`flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between ${
                  active ? "bg-brass/10" : ""
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(f.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <p
                    className={`truncate font-medium ${
                      active ? "text-brass" : "text-paper"
                    }`}
                    style={{ overflowWrap: "anywhere" }}
                  >
                    {f.name}
                  </p>
                  <p className="mt-0.5 font-mono text-[11px] text-paper/40">
                    {f.snapshots?.length || 0} version
                    {(f.snapshots?.length || 0) === 1 ? "" : "s"} ·{" "}
                    {formatTime(f.created_at)}
                  </p>
                </button>
                <div className="flex shrink-0 items-center gap-1">
                  <span className="mr-2 font-mono text-xs text-paper/55">
                    v{f.latest_version ?? "—"}
                  </span>
                  <VersionButton
                    disabled={busy}
                    label={`New version of ${f.name}`}
                    onClick={() => startVersion(f)}
                  />
                  <TrashButton
                    disabled={busy}
                    label={`Delete ${f.name}`}
                    onClick={() => onDelete(f)}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
