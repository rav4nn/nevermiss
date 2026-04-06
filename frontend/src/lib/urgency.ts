export type UrgencyTier =
  | "critical"
  | "urgent"
  | "soon"
  | "on_radar"
  | "passive"
  | "recently_expired";

export type UrgencyResult = {
  tier: UrgencyTier;
  daysRemaining: number;
};

function getTodayInTimezone(userTimezone: string): Date {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: userTimezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = formatter.formatToParts(new Date());
  const year = Number(parts.find((part) => part.type === "year")?.value);
  const month = Number(parts.find((part) => part.type === "month")?.value);
  const day = Number(parts.find((part) => part.type === "day")?.value);
  return new Date(Date.UTC(year, month - 1, day));
}

function parseIsoDate(dateString: string): Date {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

export function computeUrgency(
  expiryDate: string,
  userTimezone: string,
): UrgencyResult | null {
  const expiry = parseIsoDate(expiryDate);
  const today = getTodayInTimezone(userTimezone);
  const daysRemaining = Math.round(
    (expiry.getTime() - today.getTime()) / 86_400_000,
  );

  if (daysRemaining < -90) {
    return null;
  }
  if (daysRemaining < 0) {
    return { tier: "recently_expired", daysRemaining };
  }
  if (daysRemaining < 7) {
    return { tier: "critical", daysRemaining };
  }
  if (daysRemaining < 30) {
    return { tier: "urgent", daysRemaining };
  }
  if (daysRemaining < 90) {
    return { tier: "soon", daysRemaining };
  }
  if (daysRemaining < 365) {
    return { tier: "on_radar", daysRemaining };
  }
  return { tier: "passive", daysRemaining };
}

export const urgencyConfig: Record<
  UrgencyTier,
  { label: string; color: string; bgColor: string }
> = {
  critical: {
    label: "Critical",
    color: "text-red-700 border-red-500",
    bgColor: "bg-red-100",
  },
  urgent: {
    label: "Urgent",
    color: "text-orange-700 border-orange-500",
    bgColor: "bg-orange-100",
  },
  soon: {
    label: "Soon",
    color: "text-yellow-700 border-yellow-500",
    bgColor: "bg-yellow-100",
  },
  on_radar: {
    label: "On radar",
    color: "text-green-700 border-green-500",
    bgColor: "bg-green-100",
  },
  passive: {
    label: "Passive",
    color: "text-stone-700 border-stone-400",
    bgColor: "bg-stone-100",
  },
  recently_expired: {
    label: "Recently expired",
    color: "text-slate-700 border-slate-400",
    bgColor: "bg-slate-200",
  },
};
