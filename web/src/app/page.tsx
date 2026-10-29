import Link from "next/link";
import { ArrowRight, BadgeCheck, Banknote, ClipboardCheck, CloudSun, HeartHandshake, ShieldCheck, Sparkles } from "lucide-react";
import { AirQualityMascot } from "@/components/air-quality-mascot";
import { ContactForm } from "@/components/contact-form";
import { FaqAccordion } from "@/components/faq-accordion";
import { LandingNavbar } from "@/components/landing-navbar";
import { TeamGrid } from "@/components/team-grid";
import { TrendChart } from "@/components/trend-chart";
import { ZonePicker } from "@/components/zone-picker";
import { money } from "@/lib/format";
import { fillDailyReadings, getApiBand, getIllustrativeReadings, getRecentDateRange } from "@/lib/air-quality";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function HomePage({ searchParams }: { searchParams: Promise<{ zone?: string }> }) {
  const params = await searchParams;
  const supabase = await createClient();
  const [{ data: zones, error: zoneError }, { data: plans, error: planError }] = await Promise.all([
    supabase.from("zones").select("id,name,state").order("name"),
    supabase.from("plans").select("id,name,plan_type,price,description").order("price"),
  ]);
  if (zoneError || planError) throw new Error(`Could not load HazeShield information: ${zoneError?.message ?? planError?.message}`);
  const selectedZone = zones?.find((zone) => zone.id === params.zone) ?? zones?.[0];
  const chartDates = getRecentDateRange(7);
  const { data: readings, error: readingError } = selectedZone
    ? await supabase.from("readings").select("reading_date,api_value,source").eq("zone_id", selectedZone.id).gte("reading_date", chartDates[0]).lte("reading_date", chartDates[chartDates.length - 1]).order("reading_date", { ascending: false })
    : { data: [], error: null };
  if (readingError) throw new Error(`Could not load air-quality data: ${readingError.message}`);
  const storedReadingsByDate = new Map((readings ?? []).map((reading) => [reading.reading_date, reading]));
  const displayReadings = selectedZone
    ? getIllustrativeReadings(selectedZone.id, chartDates)
      .map((reading) => storedReadingsByDate.get(reading.reading_date) ?? reading)
      .reverse()
    : [];
  const latest = displayReadings[0];
  const score = latest?.api_value;
  const band = getApiBand(score);

  return (
    <div className="landing-page">
      <LandingNavbar />
      <div className="landing-container">
        <section className="landing-hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">HazeShield · Malaysia</p>
            <h1 id="hero-title">When haze stops you earning, HazeShield keeps you paid.</h1>
            <p className="hero-description">If the air quality index (API) stays above 150 for two days in a row in your zone, you get paid. No paperwork. No medical claim.</p>
            <div className="button-row">
              <Link className="button" href="/signup">Get started <ArrowRight size={18} aria-hidden="true" /></Link>
              <Link className="button secondary" href="#how-it-works">How it works</Link>
            </div>
            <p className="hero-note"><ShieldCheck size={17} aria-hidden="true" /> Parametric income-protection prototype for Malaysian outdoor workers</p>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="hero-sun"><CloudSun size={82} strokeWidth={1.35} /></div>
            <div className="hero-sparkle"><Sparkles size={26} /></div>
            <div className="hero-promise"><strong>API 150+</strong><span>for 2 days in a row</span></div>
          </div>
        </section>

        <section className="landing-section" id="how-it-works" aria-labelledby="how-title">
          <div className="section-heading">
            <p className="eyebrow">How it works</p>
            <h2 id="how-title">Three steps. No claims to file.</h2>
            <p>A simple parametric trigger is designed to support you when haze disrupts outdoor work.</p>
          </div>
          <div className="steps-grid">
            <article className="info-card step-card">
              <span className="icon-tile"><ClipboardCheck size={25} aria-hidden="true" /></span>
              <span className="step-number">01</span>
              <h3>Sign up and choose your zone</h3>
              <p>Tell us where you work so the relevant zone can be selected.</p>
            </article>
            <article className="info-card step-card">
              <span className="icon-tile"><BadgeCheck size={25} aria-hidden="true" /></span>
              <span className="step-number">02</span>
              <h3>Pick a plan</h3>
              <p>Review the available plan details and choose a starting point.</p>
            </article>
            <article className="info-card step-card">
              <span className="icon-tile"><Banknote size={25} aria-hidden="true" /></span>
              <span className="step-number">03</span>
              <h3>Get paid automatically when the trigger is met</h3>
              <p>When API stays above 150 for two consecutive days in your zone, the prototype simulates a payout.</p>
            </article>
          </div>
        </section>

        <section className="landing-section plans-section" id="plans" aria-labelledby="plans-title">
          <div className="section-heading">
            <p className="eyebrow">Plans</p>
            <h2 id="plans-title">Choose a starting point.</h2>
            <p>Browse the current prototype plans. Pricing and payouts are simulated.</p>
          </div>
          <div className="plans-grid">
            {plans?.map((plan) => (
              <article className="info-card plan-card" key={plan.id}>
                <p className="eyebrow">{plan.plan_type === "group" ? "Employer" : "Individual"}</p>
                <h3>{plan.name}</h3>
                <p className="plan-price">{money(plan.price)}<span> / month</span></p>
                <p>{plan.description}</p>
                <Link className="button secondary" href={`/signup?type=${plan.plan_type === "group" ? "employer" : "individual"}`}>Choose {plan.name}</Link>
              </article>
            ))}
            {!plans?.length && <p className="info-card">Plans are not available right now.</p>}
          </div>
        </section>

        <section className="snapshot-section" aria-labelledby="snapshot-title">
          <div className="section-heading">
            <p className="eyebrow">Zone snapshot · Prototype data</p>
            <h2 id="snapshot-title">See the haze trigger in context.</h2>
            <p>Stored readings are shown where available; missing dates use illustrative values. Nothing here determines a real-world payout.</p>
          </div>
          <ZonePicker zones={zones ?? []} selectedZoneId={selectedZone?.id} />
          <div className="zone-overview">
            <article className="reading card">
              <p className="eyebrow">{selectedZone ? `${selectedZone.name} · ${selectedZone.state}` : "Air quality"}</p>
              <div className="reading-content">
                <div className="reading-details">
                  <span className="reading-value" style={{ color: band.color }}>{score ?? "—"}</span>
                  <span className="badge" style={{ color: band.color, backgroundColor: band.background }}>{band.label}</span>
                  <p>{latest ? `${latest.reading_date} · ${latest.source}` : "No reading available"}</p>
                </div>
                <AirQualityMascot value={score} />
              </div>
            </article>
            {selectedZone && <div className="chart-section"><TrendChart title={`${selectedZone.name} daily API`} points={fillDailyReadings(displayReadings, chartDates)} /></div>}
          </div>
        </section>

        <section className="landing-section about-section" id="about" aria-labelledby="about-title">
          <div className="about-intro">
            <div className="section-heading">
              <p className="eyebrow">About us</p>
              <h2 id="about-title">Income protection that starts with people.</h2>
            </div>
            <div className="mission-card">
              <span className="icon-tile"><HeartHandshake size={26} aria-hidden="true" /></span>
              <p className="eyebrow">Our mission</p>
              <p className="mission-statement">When haze stops outdoor workers from earning, HazeShield keeps them paid.</p>
            </div>
          </div>
          <div className="about-copy">
            <div>
              <h3>Why we exist</h3>
              <p>Haze can force gig and daily-wage workers to choose between lost income and health risk, while traditional insurance rarely covers them. We are exploring a simpler, transparent way to support income resilience when air quality interrupts outdoor work.</p>
            </div>
            <div className="values-grid">
              <article className="info-card value-card"><Banknote size={23} aria-hidden="true" /><h3>Fast</h3><p>Designed for payout within 24 hours of a qualifying trigger.</p></article>
              <article className="info-card value-card"><HeartHandshake size={23} aria-hidden="true" /><h3>Affordable</h3><p>Designed around low monthly premiums.</p></article>
              <article className="info-card value-card"><ClipboardCheck size={23} aria-hidden="true" /><h3>Stress-free</h3><p>No paperwork and no medical claim in the prototype flow.</p></article>
            </div>
            <div className="story-card">
              <p className="eyebrow">Our story</p>
              <p>HazeShield began as a BFM3130 Entrepreneurship in FinTech project at Monash University Malaysia.</p>
            </div>
          </div>
          <div className="roadmap" aria-label="Project roadmap">
            <h3>Where we are headed</h3>
            <ol>
              <li><span>01</span>Prototype</li>
              <li><span>02</span>Proposed insurer partnership</li>
              <li><span>03</span>Regulatory sandbox</li>
              <li><span>04</span>More zones and perils</li>
            </ol>
          </div>
        </section>

        <section className="landing-section team-section" id="team" aria-labelledby="team-title">
          <div className="section-heading">
            <p className="eyebrow">The people behind the project</p>
            <h2 id="team-title">Meet our team.</h2>
            <p>We are working together to explore a more resilient future for outdoor workers.</p>
          </div>
          <TeamGrid />
        </section>

        <section className="landing-section faq-section" id="faq" aria-labelledby="faq-title">
          <div className="section-heading">
            <p className="eyebrow">FAQ</p>
            <h2 id="faq-title">Good questions, clear answers.</h2>
          </div>
          <FaqAccordion />
        </section>

        <section className="landing-section contact-section" id="contact" aria-labelledby="contact-title">
          <div className="contact-copy">
            <p className="eyebrow">Contact</p>
            <h2 id="contact-title">Let’s keep the conversation going.</h2>
            <p>Have a question about the project? Send us a note and we’ll be in touch.</p>
            <p className="contact-email">Email: <span>[team email]</span></p>
          </div>
          <ContactForm />
        </section>
      </div>
      <footer className="landing-footer">
        <div className="landing-footer-main">
          <Link className="footer-brand" href="/" aria-label="HazeShield home">
            <img src="/hazeshield-logo.png" alt="HazeShield logo" width="72" height="48" />
            <span>HazeShield</span>
          </Link>
          <nav aria-label="Footer navigation" className="footer-links">
            <Link href="#how-it-works">How it works</Link>
            <Link href="#plans">Plans</Link>
            <Link href="#about">About us</Link>
            <Link href="#team">Team</Link>
            <Link href="#faq">FAQ</Link>
            <Link href="#contact">Contact</Link>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
          </nav>
          <p className="disclaimer">Prototype for educational purposes. Not an insurance offer. Readings and payouts are simulated.</p>
        </div>
        <div className="copyright">© 2026 HazeShield</div>
      </footer>
    </div>
  );
}
