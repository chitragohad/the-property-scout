import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep deploys green if ESLint rules drift; CI/local `next lint` still catches issues.
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
