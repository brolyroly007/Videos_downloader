import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Salida standalone: el Dockerfile copia /app/.next/standalone.
  output: "standalone",
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
};

export default nextConfig;
