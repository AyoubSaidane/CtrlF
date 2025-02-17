/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      path: false,
      canvas: false,
    };

    // Support for PDF.js worker
    config.module.rules.push({
      test: /pdf\.worker\.(min\.)?js/,
      type: 'asset/resource'
    });

    return config;
  },
  experimental: {
    esmExternals: true
  }
};

module.exports = nextConfig;
