import Link from "next/link";

export default function TermsPage() {
  return (
    <article className="legal-page">
      <p className="eyebrow">Terms</p>
      <h1>Prototype terms</h1>
      <p>HazeShield is a prototype for educational purposes. It is not an insurance offer, insurance policy, financial product, or promise of benefits.</p>
      <h2>Demonstration only</h2>
      <p>Air-quality readings, plan prices, eligibility, and payouts displayed on this website are simulated and may be incomplete or inaccurate. No real premium is collected and no real payout is made. Do not rely on this prototype for health, safety, financial, or insurance decisions.</p>
      <h2>Availability and contact</h2>
      <p>Prototype features may change or become unavailable. Nothing on this website claims a signed insurer partnership; any partnership described is proposed only. Questions can be sent to <span>[team email]</span>.</p>
      <Link className="button secondary" href="/">Back to HazeShield</Link>
    </article>
  );
}
