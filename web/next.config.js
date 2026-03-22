/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow the app to call your Flask backend during SSR
  async headers() {
    return [];
  },
};

module.exports = nextConfig;
