import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Traces and copies only each route's actually-used dependencies into
  // .next/standalone (a self-contained server.js + minimal node_modules)
  // instead of requiring the full node_modules tree in the final image —
  // see frontend/Dockerfile's runner stage.
  output: "standalone",
};

export default nextConfig;
