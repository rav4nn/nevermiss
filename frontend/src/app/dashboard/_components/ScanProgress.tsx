"use client";

import type { ScanJob } from "@/hooks/useScanStatus";

type ScanProgressProps = {
  scanJob: ScanJob | null;
  isStarting?: boolean;
};

export function ScanProgress({
  scanJob,
  isStarting = false,
}: ScanProgressProps) {
  const emailsTotal = scanJob?.emailsTotal ?? 0;
  const emailsProcessed = scanJob?.emailsProcessed ?? 0;
  const itemsFound = scanJob?.itemsFound ?? 0;

  const isIndexing = !isStarting && emailsTotal === 0;
  const isDeterminate = emailsTotal > 0;
  const ratio = isDeterminate ? Math.min(emailsProcessed / emailsTotal, 1) : 0;
  const pct = Math.round(ratio * 100);

  let headline: string;
  if (isStarting && !scanJob) {
    headline = "Starting your first scan…";
  } else if (isIndexing) {
    headline = "Indexing your inbox…";
  } else {
    headline = `Scanning ${emailsProcessed.toLocaleString()} of ${emailsTotal.toLocaleString()} emails`;
  }

  return (
    <section className="overflow-hidden rounded-[32px] border border-slate-200 bg-slate-950 p-8 text-white shadow-[0_30px_90px_-45px_rgba(15,23,42,0.9)]">
      <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-300" />
            </span>
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-300">
              Inbox scan in progress
            </p>
          </div>
          <div className="space-y-2">
            <h2 className="text-3xl font-semibold tracking-tight">{headline}</h2>
            <p className="max-w-2xl text-sm text-slate-300">
              {isIndexing
                ? "Finding all emails in the scan window — this takes a few seconds…"
                : "We only read what we need to detect deadlines, subscriptions, and renewals. Email bodies are never stored."}
            </p>
          </div>
        </div>

        <div className="grid min-w-[280px] grid-cols-3 gap-3 text-sm">
          <div className="rounded-2xl bg-white/10 p-4">
            <p className="text-slate-300">Total</p>
            <p className="mt-2 text-2xl font-semibold">
              {emailsTotal > 0 ? emailsTotal.toLocaleString() : "—"}
            </p>
          </div>
          <div className="rounded-2xl bg-white/10 p-4">
            <p className="text-slate-300">Scanned</p>
            <p className="mt-2 text-2xl font-semibold">{emailsProcessed.toLocaleString()}</p>
          </div>
          <div className="rounded-2xl bg-white/10 p-4">
            <p className="text-slate-300">Found</p>
            <p className="mt-2 text-2xl font-semibold">{itemsFound}</p>
          </div>
        </div>
      </div>

      <div className="mt-8 space-y-2">
        <div className="h-3 overflow-hidden rounded-full bg-white/10">
          {isDeterminate ? (
            <div
              className="h-full rounded-full bg-gradient-to-r from-amber-300 via-orange-400 to-rose-500 transition-all duration-700 ease-out"
              style={{ width: `${Math.max(pct, 3)}%` }}
            />
          ) : (
            <div className="h-full w-full overflow-hidden rounded-full">
              <div className="h-full w-1/3 animate-[shimmer_1.4s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-transparent via-amber-300/60 to-transparent" />
            </div>
          )}
        </div>
        <div className="flex justify-between text-xs text-slate-400">
          <span>
            {isDeterminate ? `${pct}% complete` : isIndexing ? "Counting emails…" : "Connecting…"}
          </span>
          {isDeterminate && emailsTotal > 0 && (
            <span>{(emailsTotal - emailsProcessed).toLocaleString()} remaining</span>
          )}
        </div>
      </div>
    </section>
  );
}
