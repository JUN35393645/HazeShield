import type { Metadata, Viewport } from "next";
import Link from "next/link";
import Image from "next/image";
import { OfflineRegistration } from "@/components/offline-registration";
import "./globals.css";

export const metadata: Metadata = {
  title: "HazeShield",
  description: "Haze cover information and account dashboard for outdoor workers.",
  applicationName: "HazeShield",
  icons: { icon: "/stickers/good.png", apple: "/stickers/good.png" },
  appleWebApp: { capable: true, title: "HazeShield", statusBarStyle: "default" },
};

export const viewport: Viewport = { themeColor: "#176b52", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <OfflineRegistration />
        <header className="topbar">
          <Link className="brand" href="/"><Image src="/stickers/good.png" alt="" width={512} height={512} /><span>HazeShield</span></Link>
          <nav aria-label="Main navigation">
            <Link href="/">Home</Link><Link href="/dashboard">My account</Link>
            <Link className="nav-button" href="/login">Sign in</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="footer">Prototype only · No insurance cover or funds are issued or transferred.</footer>
      </body>
    </html>
  );
}
