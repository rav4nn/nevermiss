"use client";

import { useState } from "react";

import type { ExtractedItem } from "@/hooks/useItems";
import { urgencyConfig } from "@/lib/urgency";

type ItemCardProps = {
  item: ExtractedItem;
  primaryActionLabel: string;
  onPrimaryAction: (itemId: string) => Promise<void>;
  primaryActionVariant?: "danger" | "neutral";
  onExport?: (itemId: string) => Promise<void>;
  exportDisabled?: boolean;
};

function formatExpiryLabel(item: ExtractedItem): string {
  const date = new Date(`${item.expiryDate}T00:00:00Z`);
  const label =
    item.dateType.charAt(0).toUpperCase() + item.dateType.slice(1).replaceAll("_", " ");

  return `${label}: ${new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date)}`;
}

function formatSourceDate(sourceDate: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(sourceDate));
}

function formatDaysRemaining(daysRemaining: number): string {
  if (daysRemaining < 0) {
    const absoluteDays = Math.abs(daysRemaining);
    return `${absoluteDays} day${absoluteDays === 1 ? "" : "s"} ago`;
  }

  if (daysRemaining === 0) {
    return "Today";
  }

  return `In ${daysRemaining} day${daysRemaining === 1 ? "" : "s"}`;
}

export function ItemCard({
  item,
  primaryActionLabel,
  onPrimaryAction,
  primaryActionVariant = "danger",
  onExport,
  exportDisabled = false,
}: ItemCardProps) {
  const [isPrimaryPending, setIsPrimaryPending] = useState(false);
  const [isExportPending, setIsExportPending] = useState(false);

  const urgency = urgencyConfig[item.urgency];

  async function handlePrimaryAction() {
    setIsPrimaryPending(true);
    try {
      await onPrimaryAction(item.id);
    } finally {
      setIsPrimaryPending(false);
    }
  }

  async function handleExport() {
    if (!onExport) {
      return;
    }

    setIsExportPending(true);
    try {
      await onExport(item.id);
    } finally {
      setIsExportPending(false);
    }
  }

  return (
    <article
      className={`relative overflow-hidden rounded-[28px] border bg-white/90 p-6 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.45)] backdrop-blur ${urgency.color}`}
    >
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-amber-300 via-rose-400 to-orange-500" />
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${urgency.bgColor} ${urgency.color}`}
            >
              {urgency.label}
            </span>
            <span className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
              {item.category}
            </span>
          </div>

          <div className="space-y-2">
            <h3 className="text-2xl font-semibold tracking-tight text-slate-950">
              {item.name}
            </h3>
            <p className="text-sm text-slate-600">{formatExpiryLabel(item)}</p>
            <p className="text-sm font-medium text-slate-900">
              {formatDaysRemaining(item.daysRemaining)}
            </p>
          </div>

          <div className="max-w-2xl rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Found in email from{" "}
            <span className="font-medium text-slate-900">{item.sourceSender}</span> on{" "}
            <span className="font-medium text-slate-900">
              {formatSourceDate(item.sourceDate)}
            </span>
          </div>
        </div>

        <div className="flex min-w-[220px] flex-col gap-3">
          {onExport ? (
            <button
              type="button"
              onClick={handleExport}
              disabled={isExportPending || exportDisabled}
              className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isExportPending ? "Exporting..." : "Export to Calendar"}
            </button>
          ) : null}

          <button
            type="button"
            onClick={handlePrimaryAction}
            disabled={isPrimaryPending}
            className={`rounded-2xl border px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed ${
              primaryActionVariant === "danger"
                ? "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:border-rose-100 disabled:text-rose-300"
                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:border-slate-100 disabled:text-slate-300"
            }`}
          >
            {isPrimaryPending ? `${primaryActionLabel}...` : primaryActionLabel}
          </button>
        </div>
      </div>
    </article>
  );
}
