const isCapacitorBuild = process.env.BUILD_TARGET === 'capacitor';

/** @type {import('next').NextConfig} */
const nextConfig = isCapacitorBuild
  ? {
      // Static export for bundling into the Capacitor iOS shell.
      // Vercel-only features (redirects, rewrites, image optimization) don't
      // apply — there is no server at runtime once this is packaged natively.
      output: 'export',
      images: {
        unoptimized: true,
      },
    }
  : {
      images: {
        remotePatterns: [
          {
            protocol: 'https',
            hostname: 'storage.googleapis.com',
          },
        ],
      },
      async redirects() {
        return [
          {
            // Redirect old domain to new domain
            source: '/:path*',
            has: [
              {
                type: 'host',
                value: 'www.emergencymedicineapp.com',
              },
            ],
            destination: 'https://www.emergencymedicine.app/:path*',
            permanent: true,
          },
          {
            source: '/:path*',
            has: [
              {
                type: 'host',
                value: 'emergencymedicineapp.com',
              },
            ],
            destination: 'https://www.emergencymedicine.app/:path*',
            permanent: true,
          },
        ];
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
