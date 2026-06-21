/**
 * Central Axios instance — the single API abstraction layer.
 *
 * SSR-via-BFF model:
 *  - Browser (Client Components / TanStack Query) → NEXT_PUBLIC_API_URL
 *  - Server (Server Components / route handlers)   → BACKEND_INTERNAL_URL
 *
 * The JWT (issued after magic-link verification) is attached from an httpOnly
 * cookie on the server and from the in-memory/session store on the client.
 */
import axios, { type AxiosInstance } from "axios";

const isServer = typeof window === "undefined";

export const API_BASE_URL = isServer
  ? process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000/api"
  : process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export function createApiClient(token?: string): AxiosInstance {
  const client = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true,
    headers: { "Content-Type": "application/json" },
  });

  if (token) {
    client.defaults.headers.common.Authorization = `Bearer ${token}`;
  }

  client.interceptors.response.use(
    (res) => res,
    (error) => {
      // Normalize backend error shape for the UI error layer.
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail ?? error.message;
      return Promise.reject({ status, detail, raw: error });
    },
  );

  return client;
}

// Default browser client (no token bound; auth added per-request via hooks).
export const api = createApiClient();
