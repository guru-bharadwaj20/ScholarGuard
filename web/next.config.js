/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy API calls to the FastAPI bridge in local dev, so the browser talks
  // to one origin and EventSource needs no CORS preflight.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8000/:path*" },
    ];
  },
};

module.exports = nextConfig;
