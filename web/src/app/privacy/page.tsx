import Link from "next/link";

export default function PrivacyPage() {
  return (
    <article className="legal-page">
      <p className="eyebrow">Privacy</p>
      <h1>Privacy notice</h1>
      <p>HazeShield is an educational prototype. This short notice explains the personal information that may be collected when you use the website.</p>
      <h2>Information and purpose</h2>
      <p>If you create an account, the prototype may collect your name, email address, password, account type, occupation or business details, and selected work zone. This information is used to provide prototype account features and demonstrate the HazeShield experience. Air-quality readings and payout activity shown in the prototype are simulated.</p>
      <p>If you send a message through the contact form, your name, email, and message are only handled in your browser; the form does not transmit or store them.</p>
      <h2>Storage and choices</h2>
      <p>Account information may be stored by the services used to operate the prototype. Do not submit sensitive personal information. You may stop using the prototype at any time. For a privacy question or request, contact <span>[team email]</span>.</p>
      <p>This notice is a plain-language project summary, not legal advice. Malaysian personal data is handled with the Personal Data Protection Act 2010 (PDPA) in mind.</p>
      <Link className="button secondary" href="/">Back to HazeShield</Link>
    </article>
  );
}
