/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async redirects() {
    return [
      { source: "/borrowers", destination: "/workspace", permanent: false },
      { source: "/borrowers/:id", destination: "/workspace/:id", permanent: false },
      { source: "/strategy", destination: "/optimization", permanent: false },
      { source: "/workflows", destination: "/approvals", permanent: false },
      { source: "/chat", destination: "/assistant", permanent: false },
    ];
  },
};

module.exports = nextConfig;
