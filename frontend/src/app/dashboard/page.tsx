"use client";

import { useEffect, useMemo, useRef } from "react";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams, type ReadonlyURLSearchParams } from "next/navigation";

import { FilterBar } from "@/app/dashboard/_components/FilterBar";
import { ItemCard } from "@/app/dashboard/_components/ItemCard";
import { ScanProgress } from "@/app/dashboard/_components/ScanProgress";
import {
  useItems,
  useDismissItem,
  type ItemCategory,
  type UrgencyTier,
} from "@/hooks/useItems";
import { useMe } from "@/hooks/useMe";
import { useScanStatus, useStartScan } from "@/hooks/useScanStatus";
import { apiFetch, ApiError } from "@/lib/api-client";

type ExportResult = {
  gcalEventId: string;
  htmlLink: string;
};

function parseListParam<T extends string>(
  searchParams: ReadonlyURLSearchParams,
  key: string,
): T[] {
  const value = searchParams.get(key);
  if (!value) {
    return [];
  }

  return value
    .split(",")
    .map((entry: string) => entry.trim())
    .filter(Boolean) as T[];
}

export default function DashboardPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const autoStartedRef = useRef(false);

  const selectedCategories = useMemo(
    () => parseListParam<ItemCategory>(searchParams, "categories"),
    [searchParams],
  );
  const selectedUrgency = useMemo(
    () => parseListParam<UrgencyTier>(searchParams, "urgency"),
    [searchParams],
  );

  const meQuery = useMe();
  const itemsQuery = useItems({
    categories: selectedCategories,
    urgency: selectedUrgency,
    refetchInterval: currentScanJob?.status === "running" ? 5000 : false,
  });
  const dismissItem = useDismissItem();
  const scanStatus = useScanStatus();
  const startScan = useStartScan();

  const exportItem = useMutation({
    mutationFn: (itemId: string) =>
      apiFetch<ExportResult>(`/api/items/${itemId}/export`, { method: "POST" }),
  });

  const currentScanJob =
    scanStatus.data?.status === "queued" || scanStatus.data?.status === "running"
      ? scanStatus.data
      : null;

  useEffect(() => {
    if (
      autoStartedRef.current ||
      scanStatus.isLoading ||
      scanStatus.data !== null ||
      startScan.isPending
    ) {
      return;
    }

    autoStartedRef.current = true;
    startScan.mutate(
      { kind: "initial" },
      {
        onSettled: async () => {
          await queryClient.invalidateQueries({ queryKey: ["scan-status"] });
          await queryClient.invalidateQueries({ queryKey: ["items"] });
        },
      },
    );
  }, [queryClient, scanStatus.data, scanStatus.isLoading, startScan]);

  async function handleDismiss(itemId: string) {
    await dismissItem.mutateAsync(itemId);
  }

  async function handleExport(itemId: string) {
    const result = await exportItem.mutateAsync(itemId);
    window.open(result.htmlLink, "_blank", "noopener,noreferrer");
  }

  async function handleManualScan() {
    await startScan.mutateAsync({ kind: "manual" });
    await queryClient.invalidateQueries({ queryKey: ["scan-status"] });
  }

  const scanError =
    startScan.error instanceof ApiError
      ? startScan.error.message
      : scanStatus.data?.status === "failed"
        ? scanStatus.data.error
        : null;

  const isScanning = Boolean(currentScanJob) || startScan.isPending;
  const showItems = true; // always show found items, even while scanning

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(251,146,60,0.18),_transparent_22%),linear-gradient(180deg,_#fffaf2_0%,_#f8fafc_45%,_#eef2ff_100%)] px-6 py-10 md:px-10">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="overflow-hidden rounded-[36px] border border-slate-200 bg-white/85 p-8 shadow-[0_30px_80px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                NeverMiss dashboard
              </p>
              <div className="space-y-3">
                <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
                  Your inbox finally has a memory.
                </h1>
                <p className="max-w-2xl text-base text-slate-600">
                  Track renewals, deadlines, vouchers, and subscriptions without digging through old email threads.
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              {meQuery.data?.tier === "pro" ? (
                <button
                  type="button"
                  onClick={handleManualScan}
                  disabled={startScan.isPending || Boolean(currentScanJob)}
                  className="rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                >
                  {startScan.isPending ? "Starting scan..." : "Run manual scan"}
                </button>
              ) : (
                <Link
                  href="/pricing"
                  className="rounded-2xl bg-slate-950 px-5 py-3 text-center text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  Upgrade for manual scans
                </Link>
              )}

              <Link
                href="/handled"
                className="rounded-2xl border border-slate-200 bg-white px-5 py-3 text-center text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-950"
              >
                View handled items
              </Link>
            </div>
          </div>
        </header>

        <FilterBar
          selectedCategories={selectedCategories}
          selectedUrgency={selectedUrgency}
        />

        {currentScanJob || startScan.isPending ? (
          <ScanProgress scanJob={currentScanJob} isStarting={startScan.isPending} />
        ) : null}

        {scanError ? (
          <section className="rounded-[28px] border border-rose-200 bg-rose-50 px-6 py-5 text-sm text-rose-700">
            {scanError}
          </section>
        ) : null}

        {showItems ? (
          <section className="space-y-5">
            <div className="flex flex-col gap-3 rounded-[28px] border border-slate-200 bg-white/80 px-6 py-5 shadow-[0_20px_60px_-42px_rgba(15,23,42,0.35)] backdrop-blur sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-slate-500">
                  {isScanning ? "Items found so far" : "Active items"}
                </p>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
                  {itemsQuery.data?.total ?? 0} items need attention
                </h2>
              </div>
              <Link
                href="/settings"
                className="text-sm font-medium text-slate-600 underline-offset-4 hover:text-slate-950 hover:underline"
              >
                Update timezone and digest settings
              </Link>
            </div>

            {itemsQuery.isLoading ? (
              <div className="grid gap-5">
                <div className="h-56 rounded-[28px] bg-white/80" />
                <div className="h-56 rounded-[28px] bg-white/80" />
              </div>
            ) : itemsQuery.data && itemsQuery.data.items.length > 0 ? (
              <div className="grid gap-5">
                {itemsQuery.data.items.map((item) => (
                  <ItemCard
                    key={item.id}
                    item={item}
                    primaryActionLabel="Dismiss"
                    onPrimaryAction={handleDismiss}
                    onExport={handleExport}
                    exportDisabled={exportItem.isPending}
                  />
                ))}
              </div>
            ) : (
              <section className="rounded-[32px] border border-dashed border-slate-300 bg-white/70 px-8 py-12 text-center">
                <h3 className="text-2xl font-semibold tracking-tight text-slate-950">
                  Nothing urgent right now
                </h3>
                <p className="mx-auto mt-3 max-w-2xl text-sm text-slate-600">
                  When NeverMiss finds subscriptions, deadlines, or renewals in your inbox, they will appear here.
                </p>
              </section>
            )}
          </section>
        ) : null}
      </div>
    </main>
  );
}
