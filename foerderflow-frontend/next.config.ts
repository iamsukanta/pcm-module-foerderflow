import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // SSR-via-BFF: Server Components call the FastAPI backend. The backend base URL
  // is read from env (server: BACKEND_INTERNAL_URL, browser: NEXT_PUBLIC_API_URL).
};

export default nextConfig;
