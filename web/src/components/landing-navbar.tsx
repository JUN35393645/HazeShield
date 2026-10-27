"use client";

import Image from "next/image";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useState } from "react";

const links = [
  { href: "/", label: "Home" },
  { href: "#how-it-works", label: "How It Works" },
  { href: "#plans", label: "Plans" },
  { href: "#about", label: "About Us" },
  { href: "#team", label: "Team" },
  { href: "#faq", label: "FAQ" },
  { href: "#contact", label: "Contact" },
];

export function LandingNavbar() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <header className="landing-header">
      <div className="landing-nav-wrap">
        <Link className="landing-brand" href="/" aria-label="HazeShield home" onClick={() => setIsOpen(false)}>
          <Image src="/hazeshield-logo.png" alt="" width={56} height={44} priority />
          <span>HazeShield</span>
        </Link>
        <button
          className="menu-toggle"
          type="button"
          aria-label={isOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={isOpen}
          aria-controls="landing-navigation"
          onClick={() => setIsOpen((open) => !open)}
        >
          {isOpen ? <X size={23} aria-hidden="true" /> : <Menu size={23} aria-hidden="true" />}
        </button>
        <nav id="landing-navigation" className={`landing-navigation${isOpen ? " is-open" : ""}`} aria-label="Main navigation">
          {links.map((link) => (
            <Link href={link.href} key={link.href} onClick={() => setIsOpen(false)}>{link.label}</Link>
          ))}
          <Link className="button nav-sign-in" href="/login">Sign in</Link>
        </nav>
      </div>
    </header>
  );
}
