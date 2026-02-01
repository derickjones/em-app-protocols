import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EM Protocols",
  description: "AI-powered emergency medicine clinical decision support",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
