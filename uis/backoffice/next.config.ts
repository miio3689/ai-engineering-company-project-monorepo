import type { NextConfig } from "next";

const allowedDevOrigins = process.env.NEXT_ALLOWED_DEV_ORIGINS?.split(",")
  .map((host) => host.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  agentRules: false,
  ...(allowedDevOrigins?.length ? { allowedDevOrigins } : {}),
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
