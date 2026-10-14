import Link from "next/link";
import Image from "next/image";
import { createClient } from "@/lib/supabase/server";
import { money } from "@/lib/format";
import { TrendChart } from "@/components/trend-chart";
import { AirQualityMascot } from "@/components/air-quality-mascot";
import { ZonePicker } from "@/components/zone-picker";
import { getApiBand } from "@/lib/air-quality";

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
  const { data: readings, error: readingError } = selectedZone
    ? await supabase.from("readings").select("reading_date,api_value,source").eq("zone_id", selectedZone.id).order("reading_date", { ascending: false }).limit(7)
    : { data: [], error: null };
  if (readingError) throw new Error(`Could not load air-quality data: ${readingError.message}`);
  const latest = readings?.[0];
  const score = latest?.api_value;
  const band = getApiBand(score);

  return (
    <div className="page-shell">
      <section className="hero hero-with-logo">
        <div>
          <p className="eyebrow">HazeShield · Malaysia</p>
          <h1>When the air turns hazy, your income needs a backup.</h1>
          <p>Browse practical personal plans, understand the haze trigger, and find protection for outdoor work.</p>
          <div className="button-row"><Link className="button" href="/signup">Get started</Link><Link className="button secondary" href="/login">Sign in</Link></div>
        </div>
        <Image className="brand-mascot" src="/hazeshield-logo.png" alt="HazeShield capybara mascot holding a shield" width={1536} height={1024} priority />
      </section>

      <section className="section">
        <p className="eyebrow">How the trigger works</p>
        <h2>Clear conditions, shown up front.</h2>
        <div className="grid three">
          <article className="card"><strong>API 150</strong><p>Air-quality trigger threshold.</p></article>
          <article className="card"><strong>2 consecutive days</strong><p>Both daily readings must pass the threshold.</p></article>
          <article className="card"><strong>{money(30)} / day</strong><p>Support amount for each qualifying day.</p></article>
        </div>
      </section>

      <section className="section">
        <p className="eyebrow">Zone snapshot</p>
        <h2>Latest reading</h2>
        <ZonePicker zones={zones ?? []} selectedZoneId={selectedZone?.id} />
        {selectedZone && <p className="muted">{selectedZone.name}, {selectedZone.state}</p>}
        <div className="reading card">
          <div><span className="reading-value" style={{ color: band.color }}>{score ?? "—"}</span><span className="badge" style={{ color: band.color, backgroundColor: band.background }}>{band.label}</span></div>
          <AirQualityMascot value={score} />
          <p>{latest ? `${latest.reading_date} · ${latest.source}` : "No reading available"}</p>
        </div>
        {readings && readings.length > 0 && <div className="chart-section"><TrendChart title={`${selectedZone?.name ?? "Zone"} daily API`} points={[...readings].reverse().map((reading) => ({ label: reading.reading_date.slice(5), value: reading.api_value }))} /></div>}
      </section>

      <section className="section">
        <p className="eyebrow">Plans</p><h2>Choose a starting point.</h2>
        <div className="grid three">{plans?.map((plan) => <article className="card plan" key={plan.id}>
          <p className="eyebrow">{plan.plan_type === "group" ? "Employer" : "Individual"}</p>
          <h3>{plan.name}</h3><p className="price">{money(plan.price)}</p><p>{plan.description}</p>
          <Link className="button secondary" href={`/signup?type=${plan.plan_type === "group" ? "employer" : "individual"}`}>Choose {plan.name}</Link>
        </article>)}</div>
      </section>
    </div>
  );
}
