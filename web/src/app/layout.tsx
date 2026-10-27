import type { Metadata, Viewport } from "next";
import Link from "next/link";
import Image from "next/image";
import { OfflineRegistration } from "@/components/offline-registration";
import "./globals.css";

export const metadata: Metadata = {
  title: "HazeShield | Haze income protection",
  description: "Explore HazeShield, a parametric haze income-protection prototype for Malaysian outdoor and gig workers.",
  applicationName: "HazeShield",
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
      { url: "/app-icon-192.png", type: "image/png", sizes: "192x192" },
      { url: "/app-icon-512.png", type: "image/png", sizes: "512x512" },
    ],
    apple: [{ url: "/app-icon-192.png", type: "image/png", sizes: "192x192" }],
  },
  openGraph: {
    title: "HazeShield | Haze income protection",
    description: "A parametric haze income-protection prototype for Malaysian outdoor and gig workers.",
    siteName: "HazeShield",
    locale: "en_MY",
    type: "website",
  },
  appleWebApp: { capable: true, title: "HazeShield", statusBarStyle: "default" },
};

export const viewport: Viewport = { themeColor: "#176b52", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <OfflineRegistration />
        <header className="topbar">
          <Link className="brand" href="/" aria-label="HazeShield home">
            <Image src="/hazeshield-logo.png" alt="HazeShield" width={1536} height={1024} priority />
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/">Home</Link><Link href="/dashboard">My account</Link>
            <Link className="nav-button" href="/login">Sign in</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="footer">HazeShield · Protection for outdoor workers</footer>
      </body>
    </html>
  );
}
