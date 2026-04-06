"use client";

import { useMemo } from "react";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { ItemCategory, UrgencyTier } from "@/hooks/useItems";
import { urgencyConfig } from "@/lib/urgency";

const CATEGORY_OPTIONS: ItemCategory[] = [
  "subscription",
  "insurance",
  "voucher",
  "warranty",
  "document",
  "finance",
  "domain",
  "membership",
  "other",
];

const URGENCY_OPTIONS: UrgencyTier[] = [
  "critical",
  "urgent",
  "soon",
  "on_radar",
  "passive",
  "recently_expired",
];

function humanizeCategory(category: ItemCategory): string {
  return category.charAt(0).toUpperCase() + category.slice(1);
}

type FilterBarProps = {
  selectedCategories: ItemCategory[];
  selectedUrgency: UrgencyTier[];
};

export function FilterBar({
  selectedCategories,
  selectedUrgency,
}: FilterBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const searchString = useMemo(() => searchParams.toString(), [searchParams]);

  function updateQueryParam(key: string, values: string[]) {
    const nextParams = new URLSearchParams(searchString);
    if (values.length > 0) {
      nextParams.set(key, values.join(","));
    } else {
      nextParams.delete(key);
    }
    const nextPath = nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname;
    router.replace(nextPath, { scroll: false });
  }

  function toggleValue(currentValues: string[], value: string, key: string) {
    const nextValues = currentValues.includes(value)
      ? currentValues.filter((current) => current !== value)
      : [...currentValues, value];

    updateQueryParam(key, nextValues);
  }

  function clearFilters() {
    const nextParams = new URLSearchParams(searchString);
    nextParams.delete("categories");
    nextParams.delete("urgency");
    router.replace(
      nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname,
      { scroll: false },
    );
  }

  return (
    <section className="rounded-[32px] border border-slate-200 bg-white/85 p-6 shadow-[0_24px_60px_-42px_rgba(15,23,42,0.45)] backdrop-blur">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
            Filter your queue
          </p>
          <h2 className="text-xl font-semibold tracking-tight text-slate-950">
            Focus on the items that need attention right now
          </h2>
        </div>

        <button
          type="button"
          onClick={clearFilters}
          className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
        >
          Clear filters
        </button>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-700">Categories</p>
          <div className="flex flex-wrap gap-2">
            {CATEGORY_OPTIONS.map((category) => {
              const checked = selectedCategories.includes(category);
              return (
                <label
                  key={category}
                  className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${
                    checked
                      ? "border-slate-950 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={() =>
                      toggleValue(selectedCategories, category, "categories")
                    }
                  />
                  {humanizeCategory(category)}
                </label>
              );
            })}
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-700">Urgency</p>
          <div className="flex flex-wrap gap-2">
            {URGENCY_OPTIONS.map((tier) => {
              const checked = selectedUrgency.includes(tier);
              return (
                <label
                  key={tier}
                  className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${
                    checked
                      ? "border-slate-950 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={() => toggleValue(selectedUrgency, tier, "urgency")}
                  />
                  {urgencyConfig[tier].label}
                </label>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
