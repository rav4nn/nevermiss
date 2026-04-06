"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";

export type User = {
  id: string;
  email: string;
  gmailAddress: string;
  tier: "free" | "pro";
  timezone: string;
  digestDayOfWeek: number;
  lastScanAt: string | null;
  createdAt: string;
};

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/me"),
  });
}
