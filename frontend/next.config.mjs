/** @type {import('next').NextConfig} */
const API_URL = process.env.API_URL || "http://127.0.0.1:8000";

const nextConfig = {
  // Investigations can take a while (LLM call), so allow a long proxy timeout.
  experimental: { proxyTimeout: 180000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
