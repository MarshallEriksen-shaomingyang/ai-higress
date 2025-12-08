import type { NextConfig } from "next";

// @ts-ignore - next-pwa doesn't have TypeScript definitions
const withPWA = require('next-pwa');

const nextConfig: NextConfig = {
  // 现有配置...
  turbopack: {},
};

export default withPWA({
  dest: "public",
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
})(nextConfig);
