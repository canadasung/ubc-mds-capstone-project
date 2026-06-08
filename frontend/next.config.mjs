/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // plotly.js ships its own minified bundle; transpiling react-plotly.js keeps
  // the App Router happy when it is dynamically imported with ssr:false.
  transpilePackages: ["react-plotly.js"],
};

export default nextConfig;
