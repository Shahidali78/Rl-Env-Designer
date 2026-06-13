import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A stray lockfile higher up the tree confuses workspace-root inference.
  turbopack: { root: __dirname },
};

export default nextConfig;
