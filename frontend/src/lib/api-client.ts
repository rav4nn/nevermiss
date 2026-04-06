"use client";

import { signOut } from "next-auth/react";

export type ApiErrorPayload = {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
};

export class ApiError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown>;

  constructor(payload: ApiErrorPayload["error"], status: number) {
    super(payload.message);
    this.name = "ApiError";
    this.code = payload.code;
    this.status = status;
    this.details = payload.details;
  }
}

type JsonBody = Record<string, unknown> | readonly unknown[];

type ApiFetchOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | JsonBody | null;
};

const AUTH_COOKIE_NAMES = [
  "__Secure-authjs.session-token",
  "authjs.session-token",
  "__Secure-next-auth.session-token",
  "next-auth.session-token",
];

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: ApiErrorPayload["error"] = {
    code: "INTERNAL",
    message: "Request failed.",
  };

  try {
    const json = (await response.json()) as unknown;
    if (isRecord(json) && isRecord(json.error)) {
      payload = {
        code:
          typeof json.error.code === "string" ? json.error.code : "INTERNAL",
        message:
          typeof json.error.message === "string"
            ? json.error.message
            : "Request failed.",
        details: isRecord(json.error.details) ? json.error.details : undefined,
      };
    }
  } catch {
    // Best-effort parsing only.
  }

  return new ApiError(payload, response.status);
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  let body = options.body;
  if (
    body &&
    typeof body === "object" &&
    !(body instanceof FormData) &&
    !(body instanceof URLSearchParams) &&
    !(body instanceof Blob) &&
    !(body instanceof ArrayBuffer) &&
    !(body instanceof ReadableStream)
  ) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  const authToken = getSessionJwtFromCookie();
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers,
    body: body as BodyInit | null | undefined,
  });

  if (!response.ok) {
    const error = await parseError(response);
    if (response.status === 401) {
      await signOut({ callbackUrl: "/login" });
    }
    throw error;
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function getSessionJwtFromCookie(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const cookies = document.cookie.split(";").map((value) => value.trim());
  for (const cookieName of AUTH_COOKIE_NAMES) {
    const match = cookies.find((cookie) => cookie.startsWith(`${cookieName}=`));
    if (match) {
      return decodeURIComponent(match.slice(cookieName.length + 1));
    }
  }

  return null;
}
