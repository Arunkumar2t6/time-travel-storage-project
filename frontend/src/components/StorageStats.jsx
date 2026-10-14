import { formatBytes } from "../api";

function Stat({ label, value, hint }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-paper/45">
        {label}
      </p>
      <p className="mt-1 truncate font-display text-2xl font-bold text-paper sm:text-3xl">
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-paper/50">{hint}</p>}
    </div>
  );
}

export default function StorageStats({ globalStats }) {
  const stats = globalStats;
  if (!stats) {
    return (
      <div className="vault-panel animate-pulse-soft p-5">
        <p className="font-mono text-xs text-paper/40">Loading savings…</p>
      </div>
    );
  }

  const logical = stats.logical_bytes ?? 0;
  const physical = stats.physical_bytes ?? 0;
  const ratio = logical > 0 ? Math.min(physical / logical, 1) : 0;

  return (
    <div className="vault-panel animate-rise p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-display text-lg font-bold text-paper">
          Storage efficiency
        </h3>
        <span className="font-mono text-xs text-brass">whole bucket</span>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-5 lg:grid-cols-4">
        <Stat label="Logical" value={formatBytes(logical)} hint="Every file, every version" />
        <Stat
          label="Physical"
          value={formatBytes(physical)}
          hint="Unique blocks on disk"
        />
        <Stat
          label="Saved"
          value={formatBytes(stats.bytes_saved)}
          hint="CoW dedup gain"
        />
        <Stat
          label="Efficiency"
          value={`${stats.savings_percent ?? 0}%`}
          hint={`${globalStats?.unique_blocks ?? 0} unique blocks`}
        />
      </div>

      <div className="mt-6">
        <div className="flex justify-between font-mono text-[10px] uppercase tracking-wider text-paper/40">
          <span>Physical share</span>
          <span>{Math.round(ratio * 100)}% of logical</span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden bg-line">
          <div
            className="h-full origin-left bg-brass transition-all duration-500"
            style={{ width: `${Math.max(ratio * 100, logical ? 2 : 0)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
