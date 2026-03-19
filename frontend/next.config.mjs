/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'storage.googleapis.com',
      },
    ],
  },
  async rewrites() {
    return [
      {
        // Proxy Firebase auth helper pages to firebaseapp.com so that
        // signInWithRedirect works on browsers blocking third-party storage
        // access (Chrome 115+, Firefox 109+, Safari 16.1+). See EMA-71.
        // The companion file public/__/firebase/init.json provides the
        // Firebase config that the auth iframe needs (Firebase Hosting is
        // not deployed for this project, so we self-host init.json).
        source: '/__/auth/:path*',
        destination: 'https://clinical-assistant-457902.firebaseapp.com/__/auth/:path*',
      },
    ];
  },
};

export default nextConfig;
