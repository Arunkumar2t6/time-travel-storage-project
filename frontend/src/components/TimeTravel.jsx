import { useMemo, useRef } from "react";
import { downloadUrl, formatBytes, formatTime } from "../api";
import { TrashButton, VersionButton } from "./ActionIcons";

export default function TimeTravel({
  file,
  version,
  onVersionChange,
  onDeleteVersion,
  onDelete,
  onVersion,
  busy,
  chunks,
}) {
  const inputRef = useRef(null);
  const snapshots = file?.snapshots || [];
  const max = Math.max(snapshots.length - 1, 0);
  const index = useMemo(() => {
    if (!snapshots.length) return 0;
    const i = snapshots.findIndex((s) => s.version_number === version);
    return i >= 0 ? i : snapshots.length - 1;
  }, [snapshots, version]);

  const current = snapshots[index];

  if (!file || !snapshots.length) {
    return (
      <div className="vault-panel flex min-h-[220px] items-center justify-center p-8 text-center">
        <p className="text-sm text-paper/50">
          Select a file to scrub its version timeline.
        </p>
      </div>
    );
  }

  return (
    <div className="vault-panel animate-rise overflow-hidden">
      <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4 sm:px-6">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-brass">
            Time-travel
          </p>
          <h3
            className="mt-1 font-display text-xl font-bold text-paper"
            style={{ overflowWrap: "anywhere" }}
          >
            {file.name}
          </h3>
        </div>
        <div className="flex shrink-0">
          <VersionButton
            disabled={busy}
            label={`New version of ${file.name}`}
            onClick={() => inputRef.current?.click()}
          />
          <TrashButton
            disabled={busy}
            label={`Delete ${file.name}`}
            onClick={() => onDelete(file)}
          />
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const picked = e.target.files?.[0];
              e.target.value = "";
              if (picked) onVersion(file, picked);
            }}
          />
        </div>
      </div>

      <div className="space-y-6 px-5 py-6 sm:px-6">
        <div>
          <div className="mb-3 flex items-end justify-between gap-3">
            <div>
              <p className="font-mono text-xs text-paper/45">Version</p>
              <p className="font-display text-4xl font-extrabold text-brass">
                v{current.version_number}
              </p>
            </div>
            <div className="text-right">
              <p className="font-mono text-xs text-paper/45">Captured</p>
              <p className="text-sm text-paper">{formatTime(current.snapshot_time)}</p>
            </div>
          </div>

          <input
            type="range"
            min={0}
            max={max}
            step={1}
            value={index}
            disabled={snapshots.length < 2}
            aria-label="Scrub file versions"
            onChange={(e) => {
              const next = snapshots[Number(e.target.value)];
              if (next) onVersionChange(next.version_number);
            }}
          />

          <div className="mt-2 flex justify-between font-mono text-[10px] text-paper/35">
            <span>v{snapshots[0].version_number}</span>
            <span>
              {snapshots.length} snapshot{snapshots.length === 1 ? "" : "s"}
            </span>
            <span>v{snapshots[snapshots.length - 1].version_number}</span>
          </div>
        </div>

        <ChunkMap report={chunks} version={current.version_number} />

        <div className="flex flex-wrap gap-2">
          <a
            className="vault-btn"
            href={downloadUrl(file.id, current.version_number)}
          >
            Download v{current.version_number}
          </a>
          {snapshots.length > 1 && (
            <button
              type="button"
              className="vault-btn-ghost"
              onClick={() =>
                onVersionChange(snapshots[snapshots.length - 1].version_number)
              }
            >
              Jump to latest
            </button>
          )}
        </div>

        <ol className="max-h-40 space-y-1 overflow-y-auto border-t border-line pt-4">
          {[...snapshots].reverse().map((s) => {
            const active = s.version_number === current.version_number;
            const summary = chunks?.versions?.find(
              (v) => v.version_number === s.version_number
            );
            return (
              <li
                key={s.id}
                className={`flex items-center gap-2 px-2 py-1 ${
                  active ? "bg-brass/15" : ""
                }`}
              >
                <button
                  type="button"
                  onClick={() => onVersionChange(s.version_number)}
                  className={`flex min-w-0 flex-1 items-center justify-between gap-3 py-1 text-left font-mono text-xs transition ${
                    active
                      ? "text-brass"
                      : "text-paper/55 hover:text-paper"
                  }`}
                >
                  <span>v{s.version_number}</span>
                  <span className="truncate">{formatTime(s.snapshot_time)}</span>
                  {summary && (
                    <span className="hidden sm:inline">
                      {summary.new_count} new · {summary.reused_count} stored
                    </span>
                  )}
                </button>
                <TrashButton
                  disabled={busy}
                  label={`Delete v${s.version_number}`}
                  onClick={() => onDeleteVersion(file, s.version_number)}
                />
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

function Meta({ label, value, hint }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-[10px] uppercase tracking-wider text-paper/40">
        {label}
      </p>
      <p className="mt-0.5 truncate text-sm font-medium text-paper">{value}</p>
      {hint && <p className="truncate font-mono text-[10px] text-paper/40">{hint}</p>}
    </div>
  );
}

function ChunkMap({ report, version }) {
  const match = report && report.version_number === version;
  if (!match) {
    return (
      <p className="border-t border-line pt-5 font-mono text-xs text-paper/40">
        Loading chunk map…
      </p>
    );
  }

  const total = report.chunk_count || 1;
  const newShare = (report.new_count / total) * 100;

  return (
    <div className="border-t border-line pt-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-paper/45">
        Chunks in v{version}
      </p>
      <div className="mt-3 grid grid-cols-3 gap-3">
        <Meta label="Created" value={report.chunk_count} />
        <Meta label="Already stored" value={report.reused_count} />
        <Meta label="New unique" value={report.new_count} />
      </div>
      <div className="mt-4 h-2 w-full bg-line">
        <div
          className="h-full bg-brass"
          style={{ width: `${newShare}%` }}
        />
      </div>
      <div className="mt-2 flex justify-between font-mono text-[10px] text-paper/40">
        <span>{report.unique_count} distinct hashes</span>
        <span>brass = new · track = stored</span>
      </div>
      {report.slots?.length > 0 && (
        <ol className="mt-3 flex flex-wrap gap-1">
          {report.slots.map((slot) => (
            <li
              key={slot.index}
              title={`#${slot.index} ${slot.status} ${slot.hash_prefix} ${formatBytes(slot.size_bytes)}`}
              className={`h-6 w-6 font-mono text-[9px] leading-6 text-center ${
                slot.status === "new"
                  ? "bg-brass text-ink"
                  : "bg-line text-paper/70"
              }`}
            >
              {slot.index}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
