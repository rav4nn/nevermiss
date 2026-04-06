"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";

export type ItemCategory =
  | "subscription"
  | "insurance"
  | "voucher"
  | "warranty"
  | "document"
  | "finance"
  | "domain"
  | "membership"
  | "other";

export type DateType = "expiry" | "renewal" | "deadline" | "end_of_offer";
export type Confidence = "high" | "medium" | "low";
export type UrgencyTier =
  | "critical"
  | "urgent"
  | "soon"
  | "on_radar"
  | "passive"
  | "recently_expired";

export type ExtractedItem = {
  id: string;
  userId: string;
  name: string;
  category: ItemCategory;
  expiryDate: string;
  dateType: DateType;
  confidence: Confidence;
  notes: string | null;
  sourceSender: string;
  sourceDate: string;
  sourceMessageId: string;
  dismissed: boolean;
  dismissedAt: string | null;
  exportedToGcal: boolean;
  gcalEventId: string | null;
  urgency: UrgencyTier;
  daysRemaining: number;
  createdAt: string;
  updatedAt: string;
};

export type ItemsResponse = {
  items: ExtractedItem[];
  total: number;
};

export type UseItemsFilters = {
  dismissed?: boolean;
  categories?: ItemCategory[];
  urgency?: UrgencyTier[];
};

function buildItemsQuery(filters: UseItemsFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.dismissed !== undefined) {
    params.set("dismissed", String(filters.dismissed));
  }
  if (filters.categories?.length) {
    params.set("categories", filters.categories.join(","));
  }
  if (filters.urgency?.length) {
    params.set("urgency", filters.urgency.join(","));
  }
  const query = params.toString();
  return query ? `/api/items?${query}` : "/api/items";
}

export function useItems(filters: UseItemsFilters = {}) {
  return useQuery({
    queryKey: ["items", filters],
    queryFn: () => apiFetch<ItemsResponse>(buildItemsQuery(filters)),
  });
}

export function useDismissItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: string) =>
      apiFetch<ExtractedItem>(`/api/items/${itemId}/dismiss`, {
        method: "POST",
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}

export function useUndismissItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: string) =>
      apiFetch<ExtractedItem>(`/api/items/${itemId}/undismiss`, {
        method: "POST",
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}
