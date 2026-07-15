import type { Metadata, Viewport } from "next";
import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import NativeLinkHandler from "@/components/NativeLinkHandler";

const isCapacitorBuild = process.env.BUILD_TARGET === "capacitor";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-title",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const inter = Inter({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "EMA",
  description: "AI-powered emergency medicine clinical decision support",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Pinch zoom doesn't feel native and there's no content that benefits
  // from it; keep it enabled on web.
  maximumScale: isCapacitorBuild ? 1 : undefined,
  userScalable: isCapacitorBuild ? false : undefined,
  // Let content draw under the notch/home indicator on native so we can
  // control the padding ourselves with env(safe-area-inset-*); harmless
  // on web since Safari only honors viewport-fit within an installed/
  // full-screen context.
  viewportFit: isCapacitorBuild ? "cover" : undefined,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark${isCapacitorBuild ? " native-app" : ""}`}>
      <head>
        <script type="text/javascript" src="https://js.live.net/v7.2/OneDrive.js" async defer></script>
      </head>
      <body className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} antialiased`}>
        <AuthProvider>
          <NativeLinkHandler />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
