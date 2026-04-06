"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { signOut } from "next-auth/react";

import { useMe } from "@/hooks/useMe";
import { apiFetch, ApiError } from "@/lib/api-client";

type SettingsResponse = {
  tier: "free" | "pro";
  hasApiKey: boolean;
  timezone: string;
  digestDayOfWeek: number;
};

type SettingsPayload = {
  apiKey?: string | null;
  timezone?: string;
  digestDayOfWeek?: number;
};

const DIGEST_DAY_OPTIONS = [
  { value: 0, label: "Sunday" },
  { value: 1, label: "Monday" },
  { value: 2, label: "Tuesday" },
  { value: 3, label: "Wednesday" },
  { value: 4, label: "Thursday" },
  { value: 5, label: "Friday" },
  { value: 6, label: "Saturday" },
];

function getTimezoneOptions(): string[] {
  const intlWithSupportedValues = Intl as typeof Intl & {
    supportedValuesOf?: (key: string) => string[];
  };

  if (typeof intlWithSupportedValues.supportedValuesOf === "function") {
    return intlWithSupportedValues.supportedValuesOf("timeZone");
  }

  return [
    "UTC",
    "America/New_York",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Kolkata",
    "Australia/Sydney",
  ];
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const meQuery = useMe();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiFetch<SettingsResponse>("/api/settings"),
  });

  const timezoneOptions = useMemo(() => getTimezoneOptions(), []);
  const [apiKey, setApiKey] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [digestDayOfWeek, setDigestDayOfWeek] = useState(1);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }

    setTimezone(settingsQuery.data.timezone);
    setDigestDayOfWeek(settingsQuery.data.digestDayOfWeek);
  }, [settingsQuery.data]);

  const saveSettings = useMutation({
    mutationFn: (payload: SettingsPayload) =>
      apiFetch<SettingsResponse>("/api/settings", {
        method: "PATCH",
        body: payload,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], data);
      setApiKey("");
      setTimezone(data.timezone);
      setDigestDayOfWeek(data.digestDayOfWeek);
      setStatusMessage("Settings saved.");
    },
  });

  const deleteAccount = useMutation({
    mutationFn: () => apiFetch<void>("/api/me", { method: "DELETE" }),
    onSuccess: async () => {
      await signOut({ callbackUrl: "/" });
    },
  });

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatusMessage(null);

    const payload: SettingsPayload = {
      timezone,
      digestDayOfWeek,
    };

    if (apiKey.trim().length > 0) {
      payload.apiKey = apiKey.trim();
    }

    await saveSettings.mutateAsync(payload);
  }

  async function handleClearApiKey() {
    setStatusMessage(null);
    await saveSettings.mutateAsync({ apiKey: null, timezone, digestDayOfWeek });
  }

  async function handleDeleteAccount() {
    if (!window.confirm("Delete your NeverMiss account permanently? This cannot be undone.")) {
      return;
    }

    await deleteAccount.mutateAsync();
  }

  const saveError =
    saveSettings.error instanceof ApiError ? saveSettings.error.message : null;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.15),_transparent_24%),linear-gradient(180deg,_#f8fafc_0%,_#ecfeff_55%,_#eef2ff_100%)] px-6 py-10 md:px-10">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="rounded-[36px] border border-slate-200 bg-white/85 p-8 shadow-[0_30px_80px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                Settings
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
                Control how NeverMiss works for you
              </h1>
              <p className="mt-3 max-w-2xl text-sm text-slate-600">
                Manage your timezone, weekly digest day, and optional Gemini API key without exposing any stored secret.
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

        <div className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
          <section className="rounded-[32px] border border-slate-200 bg-white/85 p-8 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.35)] backdrop-blur">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                Preferences
              </p>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
                Personalize your account
              </h2>
            </div>

            <form className="mt-8 space-y-6" onSubmit={handleSave}>
              <div className="space-y-3">
                <label className="text-sm font-medium text-slate-800" htmlFor="apiKey">
                  Gemini API key
                </label>
                <input
                  id="apiKey"
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={settingsQuery.data?.hasApiKey ? "Key saved" : "Enter a Gemini API key"}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:bg-white"
                />
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  {settingsQuery.data?.hasApiKey ? (
                    <span className="rounded-full bg-emerald-100 px-3 py-1 font-medium text-emerald-700">
                      Key saved
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-100 px-3 py-1 font-medium text-slate-600">
                      No key saved
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handleClearApiKey}
                    className="font-medium text-slate-600 underline-offset-4 hover:text-slate-950 hover:underline"
                  >
                    Clear saved key
                  </button>
                </div>
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-3">
                  <label className="text-sm font-medium text-slate-800" htmlFor="timezone">
                    Timezone
                  </label>
                  <select
                    id="timezone"
                    value={timezone}
                    onChange={(event) => setTimezone(event.target.value)}
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:bg-white"
                  >
                    {timezoneOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-3">
                  <label className="text-sm font-medium text-slate-800" htmlFor="digestDay">
                    Digest day
                  </label>
                  <select
                    id="digestDay"
                    value={digestDayOfWeek}
                    onChange={(event) => setDigestDayOfWeek(Number(event.target.value))}
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:bg-white"
                  >
                    {DIGEST_DAY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {saveError ? (
                <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {saveError}
                </p>
              ) : null}

              {statusMessage ? (
                <p className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                  {statusMessage}
                </p>
              ) : null}

              <button
                type="submit"
                disabled={saveSettings.isPending || settingsQuery.isLoading}
                className="rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                {saveSettings.isPending ? "Saving..." : "Save settings"}
              </button>
            </form>
          </section>

          <aside className="space-y-6">
            <section className="rounded-[32px] border border-slate-200 bg-white/85 p-8 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.35)] backdrop-blur">
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                Account
              </p>
              <div className="mt-4 space-y-3 text-sm text-slate-600">
                <p>
                  Email: <span className="font-medium text-slate-950">{meQuery.data?.email ?? "Loading..."}</span>
                </p>
                <p>
                  Tier: <span className="font-medium capitalize text-slate-950">{settingsQuery.data?.tier ?? "free"}</span>
                </p>
              </div>
            </section>

            <section className="rounded-[32px] border border-rose-200 bg-rose-50/90 p-8 shadow-[0_24px_70px_-40px_rgba(190,24,93,0.25)]">
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-rose-500">
                Danger zone
              </p>
              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-rose-950">
                Delete account
              </h2>
              <p className="mt-3 text-sm text-rose-700">
                This permanently removes your account, items, scans, and saved settings.
              </p>

              <button
                type="button"
                onClick={handleDeleteAccount}
                disabled={deleteAccount.isPending}
                className="mt-6 rounded-2xl bg-rose-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:bg-rose-300"
              >
                {deleteAccount.isPending ? "Deleting..." : "Delete account"}
              </button>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
