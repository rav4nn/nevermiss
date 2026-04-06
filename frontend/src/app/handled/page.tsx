"use client";

import Link from "next/link";

import { ItemCard } from "@/app/dashboard/_components/ItemCard";
import { useItems, useUndismissItem } from "@/hooks/useItems";

export default function HandledPage() {
  const handledItems = useItems({ dismissed: true });
  const restoreItem = useUndismissItem();

  async function handleRestore(itemId: string) {
    await restoreItem.mutateAsync(itemId);
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(148,163,184,0.16),_transparent_25%),linear-gradient(180deg,_#f8fafc_0%,_#f1f5f9_100%)] px-6 py-10 md:px-10">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="rounded-[36px] border border-slate-200 bg-white/85 p-8 shadow-[0_30px_80px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                Handled
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
                Archived items you have already dealt with
              </h1>
              <p className="mt-3 max-w-2xl text-sm text-slate-600">
                Restore anything that still needs attention and it will move back into your active queue.
              </p>
            </div>

            <Link
              href="/dashboard"
              className="rounded-2xl border border-slate-200 bg-white px-5 py-3 text-center text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-950"
            >
              Back to dashboard
            </Link>
          </div>
        </header>

        {handledItems.isLoading ? (
          <div className="grid gap-5">
            <div className="h-56 rounded-[28px] bg-white/80" />
            <div className="h-56 rounded-[28px] bg-white/80" />
          </div>
        ) : handledItems.data && handledItems.data.items.length > 0 ? (
          <div className="grid gap-5">
            {handledItems.data.items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                primaryActionLabel="Restore"
                primaryActionVariant="neutral"
                onPrimaryAction={handleRestore}
              />
            ))}
          </div>
        ) : (
          <section className="rounded-[32px] border border-dashed border-slate-300 bg-white/70 px-8 py-12 text-center">
            <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
              No handled items yet
            </h2>
            <p className="mt-3 text-sm text-slate-600">
              Dismissed items will appear here so you can restore them later if plans change.
            </p>
          </section>
        )}
      </div>
    </main>
  );
}
