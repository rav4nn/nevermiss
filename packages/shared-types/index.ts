export type UserTier = "free" | "pro";

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
export type ScanStatus = "queued" | "running" | "complete" | "failed";
export type ScanKind = "initial" | "weekly" | "manual";

export type UrgencyTier =
  | "critical"
  | "urgent"
  | "soon"
  | "on_radar"
  | "passive"
  | "recently_expired";

export interface User {
  id: string;
  email: string;
  gmailAddress: string;
  tier: UserTier;
  timezone: string;
  digestDayOfWeek: number;
  lastScanAt: string | null;
  createdAt: string;
}

export interface ExtractedItem {
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
  urgency: UrgencyTier; // computed, not stored
  daysRemaining: number; // computed
  createdAt: string;
  updatedAt: string;
}

export interface ScanJob {
  id: string;
  userId: string;
  kind: ScanKind;
  status: ScanStatus;
  emailsTotal: number;
  emailsProcessed: number;
  itemsFound: number;
  error: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

export interface LLMExtraction {
  name: string;
  category: ItemCategory;
  date: string;
  date_type: DateType;
  confidence: Confidence;
  notes: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
