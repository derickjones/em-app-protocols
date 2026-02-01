import type { Metadata } from "next";
import { Orbitron, Roboto } from "next/font/google";
import "./globals.css";

const orbitron = Orbitron({
  variable: "--font-orbitron",
  subsets: ["latin"],
  weight: ["400", "700"],
});

const roboto = Roboto({
  variable: "--font-roboto",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "Emergency Medicine App",
  description: "AI-powered emergency medicine clinical decision support",
  icons: "/favicon.ico",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${orbitron.variable} ${roboto.variable} antialiased min-h-screen flex flex-col bg-white font-sans`}>
        {children}
      </body>
    </html>
  );
}
