/** @type {import('next').NextConfig} */
const createNextIntlPlugin = require("next-intl/plugin");
const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const FLASK_API = process.env.NEXT_PUBLIC_FLASK_API_URL ?? "";

const nextConfig = {
  async rewrites() {
    if (!FLASK_API) return [];
    return [
      {
        source:      "/api/:path*",
        destination: `${FLASK_API}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              // Only load scripts from self and the Flask API origin
              `script-src 'self' 'unsafe-inline' ${FLASK_API} https://cdn.plot.ly https://telegram.org`,
              // Iframes may only embed content from self (Plotly srcdoc = same origin)
              `frame-src 'self'`,
              // Stylesheets from self only
              `style-src 'self' 'unsafe-inline'`,
              // Images from self and data URIs (Plotly exports)
              `img-src 'self' data:`,
              // API calls to self and Flask backend only
              `connect-src 'self' ${FLASK_API}`,
              `default-src 'self'`,
            ].join("; "),
          },
          {
            key: "X-Frame-Options",
            value: "SAMEORIGIN",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
        ],
      },
    ];
  },
};

module.exports = withNextIntl(nextConfig);
