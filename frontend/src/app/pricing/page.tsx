"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";

import { apiFetch } from "@/lib/api-client";

type CheckoutResponse = {
  url: string;
};

const plans = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    features: [
      "Automatic inbox scan",
      "Unlimited tracked items",
      "Dismiss and restore workflow",
      "Bring your own Gemini API key",
    ],
  },
  {
    name: "Pro",
    price: "$4",
    cadence: "per month or $36 yearly",
    features: [
      "Everything in Free",
      "Manual scans on demand",
      "Weekly digest emails",
      "Shared Gemini key included",
    ],
  },
];

export default function PricingPage() {
  const checkout = useMutation({
    mutationFn: (plan: "monthly" | "yearly") =>
      apiFetch<CheckoutResponse>("/api/billing/checkout", {
        method: "POST",
        body: { plan },
      }),
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.16),_transparent_26%),radial-gradient(circle_at_top_right,_rgba(251,191,36,0.16),_transparent_24%),linear-gradient(180deg,_#f8fafc_0%,_#eff6ff_40%,_#fff7ed_100%)] px-6 py-8 md:px-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex items-center justify-between rounded-full border border-white/70 bg-white/75 px-6 py-4 shadow-[0_18px_60px_-36px_rgba(15,23,42,0.4)] backdrop-blur">
          <Link href="/" className="text-lg font-semibold tracking-tight text-slate-950">
            NeverMiss
          </Link>
          <Link
            href="/login"
            className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Sign in
          </Link>
        </header>

        <section className="py-16">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
              Pricing
            </p>
            <h1 className="mt-4 text-5xl font-semibold tracking-tight text-slate-950">
              Choose the pace that fits your inbox
            </h1>
            <p className="mt-4 text-lg text-slate-600">
              Start free, then upgrade when you want manual scans and weekly digests delivered for you.
            </p>
          </div>

          <div className="mt-12 grid gap-6 lg:grid-cols-2">
            {plans.map((plan) => (
              <article
                key={plan.name}
                className={`rounded-[36px] border p-8 shadow-[0_30px_80px_-45px_rgba(15,23,42,0.45)] ${
                  plan.name === "Pro"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-white/60 bg-white/85 text-slate-950 backdrop-blur"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p
                      className={`text-xs font-semibold uppercase tracking-[0.35em] ${plan.name === "Pro" ? "text-slate-300" : "text-slate-500"}`}
                    >
                      {plan.name}
                    </p>
                    <h2 className="mt-4 text-4xl font-semibold tracking-tight">
                      {plan.price}
                    </h2>
                    <p
                      className={`mt-2 text-sm ${plan.name === "Pro" ? "text-slate-300" : "text-slate-600"}`}
                    >
                      {plan.cadence}
                    </p>
                  </div>
                  {plan.name === "Pro" ? (
                    <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white">
                      Most popular
                    </span>
                  ) : null}
                </div>

                <div className="mt-8 space-y-3">
                  {plan.features.map((feature) => (
                    <div
                      key={feature}
                      className={`rounded-2xl px-4 py-3 text-sm ${
                        plan.name === "Pro"
                          ? "bg-white/10 text-slate-100"
                          : "bg-slate-50 text-slate-700"
                      }`}
                    >
                      {feature}
                    </div>
                  ))}
                </div>

                {plan.name === "Pro" ? (
                  <div className="mt-8 grid gap-3 sm:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => checkout.mutate("monthly")}
                      disabled={checkout.isPending}
                      className="rounded-2xl bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      {checkout.isPending ? "Redirecting..." : "Choose monthly"}
                    </button>
                    <button
                      type="button"
                      onClick={() => checkout.mutate("yearly")}
                      disabled={checkout.isPending}
                      className="rounded-2xl border border-white/20 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:text-slate-400"
                    >
                      Choose yearly
                    </button>
                  </div>
                ) : (
                  <Link
                    href="/login"
                    className="mt-8 block rounded-2xl border border-slate-200 bg-white px-5 py-3 text-center text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-950"
                  >
                    Get started free
                  </Link>
                )}
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
