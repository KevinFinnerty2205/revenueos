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
    super(requestId ? `${message} Request ID: ${requestId}.` : message);
    this.name = "ApiClientError";
  }
}

function requestIdFor(headers: Headers): string {
  const existing = headers.get("X-Request-ID")?.trim();
  if (existing) return existing;
  return globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}`;
}

function abortError(): DOMException {
  return new DOMException("The request was cancelled.", "AbortError");
}

async function readRetryDelay(
  attempt: number,
  signal?: AbortSignal,
): Promise<void> {
  if (signal?.aborted) throw abortError();
  await new Promise<void>((resolve, reject) => {
    const onAbort = () => {
      globalThis.clearTimeout(timer);
      reject(abortError());
    };
    const timer = globalThis.setTimeout(
      () => {
        signal?.removeEventListener("abort", onAbort);
        resolve();
      },
      50 * (attempt + 1),
    );
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

async function reliableFetch(
  pathOrUrl: string,
  init: RequestInit,
): Promise<{ response: Response; requestId: string }> {
  const headers = new Headers(init.headers);
  const requestId = requestIdFor(headers);
  headers.set("X-Request-ID", requestId);
  const request = { ...init, headers };
  const method = (init.method ?? "GET").toUpperCase();
  const attempts = method === "GET" ? 3 : 1;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return {
        response: await fetch(resolveApiUrl(pathOrUrl), request),
        requestId,
      };
    } catch (reason: unknown) {
      if (init.signal?.aborted) throw abortError();
      const retryable = reason instanceof TypeError && attempt + 1 < attempts;
      if (!retryable) {
        throw new ApiClientError(
          "RevenueOS could not reach the service. Check your connection and try again.",
          0,
          "network_error",
          requestId,
        );
      }
      await readRetryDelay(attempt, init.signal ?? undefined);
    }
  }
  throw new ApiClientError(
    "RevenueOS could not reach the service. Check your connection and try again.",
    0,
    "network_error",
    requestId,
  );
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const localApiPath = !/^https?:\/\//u.test(path);
  const token = localApiPath && tokenProvider ? await tokenProvider() : null;
  const headers = new Headers(init.headers);
  if (
    init.body !== undefined &&
    init.body !== null &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const { response, requestId } = await reliableFetch(path, {
    ...init,
    cache: "no-store",
    headers,
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
      error?.requestId ?? response.headers.get("X-Request-ID") ?? requestId,
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
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const { response, requestId } = await reliableFetch(pathOrUrl, {
    ...init,
    cache: "no-store",
    headers,
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
      error?.requestId ?? response.headers.get("X-Request-ID") ?? requestId,
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

export async function apiBlob(
  pathOrUrl: string,
  init: RequestInit = { method: "GET" },
): Promise<Blob> {
  return (await apiBinaryFetch(pathOrUrl, init)).blob();
}
