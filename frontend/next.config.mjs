/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produce a standalone server bundle — needed for the multi-stage Docker
  // production image (copies only the minimal runtime, no node_modules).
  output: "standalone",
};

export default nextConfig;
