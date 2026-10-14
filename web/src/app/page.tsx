import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { money } from "@/lib/format";
import { TrendChart } from "@/components/trend-chart";

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
  const band = score == null ? "No reading" : score <= 100 ? "Good / moderate" : score <= 150 ? "Sensitive groups" : score <= 200 ? "Unhealthy" : "Very unhealthy";

  return (
    <div className="page-shell">
      <section className="hero">
        <p className="eyebrow">A prototype for Malaysia&apos;s outdoor workforce</p>
        <h1>Support when haze interrupts the workday.</h1>
        <p>Explore a simple, pre-defined haze trigger with personal or employer-sponsored cover.</p>
        <div className="button-row"><Link className="button" href="/signup">Get started</Link><Link className="button secondary" href="/login">Sign in</Link></div>
        <small>Prototype only. Plan information is indicative; no insurance cover is issued and no money is transferred.</small>
      </section>

      <section className="section">
        <p className="eyebrow">How the demo trigger works</p>
        <h2>Clear conditions, shown up front.</h2>
        <div className="grid three">
          <article className="card"><strong>API 150</strong><p>Example air-quality trigger threshold.</p></article>
          <article className="card"><strong>2 consecutive days</strong><p>Both daily readings must pass the threshold.</p></article>
          <article className="card"><strong>{money(30)} / day</strong><p>Illustrative support amount. No payments are made.</p></article>
        </div>
      </section>

      <section className="section">
        <p className="eyebrow">Zone snapshot</p>
        <h2>Latest reading</h2>
        <form action="/" method="get" className="form inline-form zone-picker">
          <label>Choose a zone<select name="zone" defaultValue={selectedZone?.id}>{zones?.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}, {zone.state}</option>)}</select></label>
          <button className="button secondary">Show readings</button>
        </form>
        {selectedZone && <p className="muted">{selectedZone.name}, {selectedZone.state}</p>}
        <div className="reading card">
          <div><span className="reading-value">{score ?? "—"}</span><span className="badge">{band}</span></div>
          <p>{latest ? `${latest.reading_date} · ${latest.source}` : "No reading available"}<br />Readings are not official health guidance.</p>
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
