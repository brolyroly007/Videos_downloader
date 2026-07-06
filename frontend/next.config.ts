import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Salida standalone: el Dockerfile copia /app/.next/standalone.
  output: "standalone",
  reactStrictMode: true,
  images: {
    // Restringido a los CDNs reales de thumbnails (antes '**' permitía
    // optimizar imágenes de cualquier host = proxy abierto).
    remotePatterns: [
      { protocol: 'https', hostname: '**.tiktokcdn.com' },
      { protocol: 'https', hostname: '**.tiktokcdn-us.com' },
      { protocol: 'https', hostname: '**.ytimg.com' },
      { protocol: 'https', hostname: '**.cdninstagram.com' },
      { protocol: 'https', hostname: '**.fbcdn.net' },
    ],
  },
};

export default nextConfig;
