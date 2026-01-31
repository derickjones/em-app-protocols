import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EM Protocol Assistant",
  description: "AI-powered emergency medicine protocol lookup - sub-2 second responses",
  icons: "/favicon.ico",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen flex flex-col bg-white">
        {children}
      </body>
    </html>
  );
}
