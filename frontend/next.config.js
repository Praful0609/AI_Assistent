/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow API calls to backend container
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
  // Standalone output for Docker production builds
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
};

module.exports = nextConfig;
