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
  const ratio =
    emailsTotal > 0 ? Math.min(emailsProcessed / emailsTotal, 1) : scanJob ? 0.15 : 0;

  return (
    <section className="overflow-hidden rounded-[32px] border border-slate-200 bg-slate-950 p-8 text-white shadow-[0_30px_90px_-45px_rgba(15,23,42,0.9)]">
      <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-300">
            Inbox scan in progress
          </p>
          <div className="space-y-2">
            <h2 className="text-3xl font-semibold tracking-tight">
              {isStarting && !scanJob
                ? "Starting your first scan..."
                : `Scanning ${emailsProcessed}/${emailsTotal} emails... ${itemsFound} items found`}
            </h2>
            <p className="max-w-2xl text-sm text-slate-300">
              We only process what we need to detect deadlines, subscriptions, and renewals. Email bodies are not kept.
            </p>
          </div>
        </div>

        <div className="grid min-w-[240px] grid-cols-2 gap-4 text-sm">
          <div className="rounded-2xl bg-white/10 p-4">
            <p className="text-slate-300">Processed</p>
            <p className="mt-2 text-2xl font-semibold">{emailsProcessed}</p>
          </div>
          <div className="rounded-2xl bg-white/10 p-4">
            <p className="text-slate-300">Items found</p>
            <p className="mt-2 text-2xl font-semibold">{itemsFound}</p>
          </div>
        </div>
      </div>

      <div className="mt-8">
        <div className="h-3 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-300 via-orange-400 to-rose-500 transition-all duration-500"
            style={{ width: `${Math.max(ratio * 100, isStarting ? 10 : 4)}%` }}
          />
        </div>
      </div>
    </section>
  );
}
