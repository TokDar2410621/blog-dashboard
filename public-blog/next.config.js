/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    typedRoutes: false,
  },
  // Allow remote images from any HTTPS source - blog covers can be from
  // Pexels, Unsplash, the user's own CDN, etc.
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
    ],
  },
  // IndexNow demands the ownership file be NAMED after the key (`<key>.txt`) at
  // the root; a file under any other name gets the submission rejected with 403.
  // The key varies per tenant, and the App Router has no partial dynamic segment
  // (`[key].txt`), so the filename is captured here and checked by the route.
  async rewrites() {
    return [
      {
        source: '/:key([0-9a-f]+).txt',
        destination: '/indexnow-key.txt?key=:key',
      },
    ];
  },
};

module.exports = nextConfig;
