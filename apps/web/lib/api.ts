import type { ApiError } from "@revenueos/shared";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
let tokenProvider: (() => Promise<string | null>) | null = null;

function apiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
    DEFAULT_API_BASE_URL
  );
}

export function resolveApiUrl(pathOrUrl: string): string {
  return /^https?:\/\//u.test(pathOrUrl)
    ? pathOrUrl
    : `${apiBaseUrl()}${pathOrUrl}`;
}

export function configureApiTokenProvider(
  provider: (() => Promise<string | null>) | null,
): void {
  tokenProvider = provider;
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
    readonly details?: Record<string, string>,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const localApiPath = !/^https?:\/\//u.test(path);
  const token = localApiPath && tokenProvider ? await tokenProvider() : null;
  const response = await fetch(resolveApiUrl(path), {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let error: ApiError | null = null;
    try {
      error = (await response.json()) as ApiError;
    } catch {
      // The public message below intentionally avoids exposing an untrusted body.
    }
    throw new ApiClientError(
      error?.message ?? "The request could not be completed.",
      response.status,
      error?.code ?? "request_failed",
      error?.requestId,
      error?.details,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function apiBinaryFetch(
  pathOrUrl: string,
  init: RequestInit,
): Promise<Response> {
  const localApiPath = !/^https?:\/\//u.test(pathOrUrl);
  const token = localApiPath && tokenProvider ? await tokenProvider() : null;
  const response = await fetch(resolveApiUrl(pathOrUrl), {
    ...init,
    cache: "no-store",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    let error: ApiError | null = null;
    try {
      error = (await response.json()) as ApiError;
    } catch {
      // The public message below intentionally avoids exposing an untrusted body.
    }
    throw new ApiClientError(
      error?.message ?? "The file request could not be completed.",
      response.status,
      error?.code ?? "file_request_failed",
      error?.requestId,
    );
  }
  return response;
}

export async function apiUpload(
  pathOrUrl: string,
  file: Blob,
  mimeType: string,
): Promise<void> {
  await apiBinaryFetch(pathOrUrl, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": mimeType },
  });
}

export async function apiBlob(pathOrUrl: string): Promise<Blob> {
  return (await apiBinaryFetch(pathOrUrl, { method: "GET" })).blob();
}
