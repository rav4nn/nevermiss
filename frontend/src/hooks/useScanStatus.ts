"use client";

import {
  useMutation,
  useQuery,
} from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api-client";

export type ScanJob = {
  id: string;
  userId: string;
  kind: "initial" | "weekly" | "manual";
  status: "queued" | "running" | "complete" | "failed";
  emailsTotal: number;
  emailsProcessed: number;
  itemsFound: number;
  error: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
};

export type StartScanPayload = {
  kind: "initial" | "manual";
};

export type StartScanResponse = {
  jobId: string;
  status: "queued";
};

export function useScanStatus() {
  return useQuery({
    queryKey: ["scan-status"],
    queryFn: async () => {
      try {
        return await apiFetch<ScanJob>("/api/scan/status");
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) {
        return false;
      }
      return job.status === "queued" || job.status === "running" ? 2000 : false;
    },
  });
}

export function useStartScan() {
  return useMutation({
    mutationFn: (payload: StartScanPayload) =>
      apiFetch<StartScanResponse>("/api/scan/start", {
        method: "POST",
        body: payload,
      }),
  });
}
