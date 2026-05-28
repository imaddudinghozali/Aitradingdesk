const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export const DEFAULT_SYMBOL =
  process.env.NEXT_PUBLIC_DEFAULT_SYMBOL || "XAUUSD";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

type RequestOptions = RequestInit & {
  cache?: RequestCache;
  next?: { revalidate?: number; tags?: string[] };
};

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = `${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(options.headers || {}),
    },
    cache: options.cache ?? "no-store",
    ...options,
  });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail, `API ${res.status} on ${path}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export async function safeFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<{ data: T | null; error: string | null }> {
  try {
    const data = await apiFetch<T>(path, options);
    return { data, error: null };
  } catch (err) {
    if (err instanceof ApiError) {
      const detail =
        typeof err.detail === "object" && err.detail && "detail" in err.detail
          ? String((err.detail as { detail: unknown }).detail)
          : String(err.detail ?? err.message);
      return { data: null, error: `${err.status}: ${detail}` };
    }
    return { data: null, error: (err as Error).message };
  }
}

export const apiBaseUrl = () => BASE_URL;
