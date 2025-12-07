/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Transpile schema types
  transpilePackages: [],

  // Optimize for production
  swcMinify: true,
}

module.exports = nextConfig
