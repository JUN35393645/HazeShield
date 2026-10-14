import Link from "next/link";
import { requireProfile } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import { formatDate, money } from "@/lib/format";
import { addTeamMember, purchasePolicy, removeTeamMember, signOut } from "@/app/actions";
import { BarChart, TrendChart } from "@/components/trend-chart";
import { AirQualityMascot } from "@/components/air-quality-mascot";
import { getApiBand } from "@/lib/air-quality";

export const dynamic = "force-dynamic";

export default async function DashboardPage({ searchParams }: { searchParams: Promise<{ error?: string; success?: string }> }) {
  const profile = await requireProfile();
  if (profile.role === "admin") return <section className="page-shell section"><div className="hero"><p className="eyebrow">Admin account</p><h1>Operations console</h1><p>Manage HazeShield accounts, policies and air-quality readings.</p><Link className="button" href="/admin">Open admin console</Link></div></section>;
  const params = await searchParams;
  const supabase = await createClient();
  const [{ data: plans, error: planError }, { data: zones, error: zoneError }, { data: policies, error: policyError }] = await Promise.all([
    supabase.from("plans").select("*").order("price"),
    supabase.from("zones").select("*").order("name"),
    supabase.from("policies").select("*,plans(name,plan_type),zones(name)").or(`user_id.eq.${profile.id},sponsor_user_id.eq.${profile.id}`).order("created_at", { ascending: false }),
  ]);
  if (planError || zoneError || policyError) throw new Error(`Could not load dashboard: ${planError?.message ?? zoneError?.message ?? policyError?.message}`);
  const today = new Date().toISOString().slice(0, 10);
  const current = (policies ?? []).filter((item) => item.status === "active" && item.start_date <= today && item.end_date >= today);
  const [{ data: payments, error: paymentError }, { data: payouts, error: payoutError }, { data: alerts, error: alertsError }] = await Promise.all([
    supabase.from("payments").select("policy_id,created_at,amount,method,status").eq("user_id", profile.id).order("created_at", { ascending: false }),
    supabase.from("payouts").select("payout_date,amount,wallet,status,policies!inner(user_id,zone_id)").eq("policies.user_id", profile.id).order("payout_date", { ascending: false }),
    supabase.from("notifications").select("message,created_at").eq("user_id", profile.id).order("created_at", { ascending: false }).limit(10),
  ]);
  if (paymentError || payoutError || alertsError) throw new Error(`Could not load account history: ${paymentError?.message ?? payoutError?.message ?? alertsError?.message}`);
  const { data: readings, error: readingError } = profile.zone_id
    ? await supabase.from("readings").select("reading_date,api_value").eq("zone_id", profile.zone_id).order("reading_date", { ascending: false }).limit(30)
    : { data: [], error: null };
  if (readingError) throw new Error(`Could not load zone trend: ${readingError.message}`);
  const latestReadingBand = readings?.[0] ? getApiBand(readings[0].api_value) : null;
  const { data: members, error: memberError } = profile.role === "employer"
    ? await supabase.from("employer_memberships").select("customer_id,status,created_at,profiles!employer_memberships_customer_id_fkey(name,email,occupation)").eq("employer_id", profile.id).order("created_at", { ascending: false })
    : { data: [], error: null };
  if (memberError) throw new Error(`Could not load team roster: ${memberError.message}`);
  const planNameByPolicyId = new Map((policies ?? []).map((policy) => [policy.id, policy.plans?.name ?? "Plan"]));

  return <div className="page-shell section">
    <div className="page-heading"><div><p className="eyebrow">{profile.role} account</p><h1>Hello, {profile.name}</h1></div><form action={signOut}><button className="button secondary">Sign out</button></form></div>
    {params.error && <p className="error notice">{params.error}</p>}{params.success && <p className="notice">{params.success}</p>}
    {profile.role === "customer" ? <>
      <div className="grid three">
        <article className="card"><p className="eyebrow">Protection status</p><strong className={current.length ? "status-good" : "status-off"}>{current.length ? "Protected" : "Not Protected"}</strong></article>
        <article className="card"><p className="eyebrow">Active cover</p><strong>{current[0] ? `${current[0].plans?.name} · through ${formatDate(current[0].end_date)}` : "No active plan"}</strong></article>
        <article className="card"><p className="eyebrow">Profile</p><strong>{profile.occupation_other || profile.occupation || "Occupation not set"}</strong><p>{zones?.find((zone) => zone.id === profile.zone_id)?.name ?? "No primary zone"}</p></article>
      </div>
      {current.some((policy) => policy.sponsor_user_id) && <p className="notice">Some of your cover is sponsored by your employer.</p>}
      <section className="section"><h2>Choose personal cover</h2>
        <form action={purchasePolicy} className="form inline-form">
          <label>Plan<select name="plan_id">{plans?.filter((plan) => plan.plan_type !== "group").map((plan) => <option key={plan.id} value={plan.id}>{plan.name} · {money(plan.price)}</option>)}</select></label>
          <label>Covered zone<select name="zone_id" defaultValue={profile.zone_id ?? ""}>{zones?.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}, {zone.state}</option>)}</select></label>
          <label>Payout wallet<select name="wallet"><option>Touch n Go</option><option>GrabPay</option><option>Boost</option></select></label>
          <button className="button">Select plan</button>
        </form>
      </section>
      {readings?.length && latestReadingBand ? <section className="section"><h2>Latest zone reading</h2><div className="card mascot-reading"><div><strong className="reading-value" style={{ color: latestReadingBand.color }}>{readings[0].api_value}</strong><span className="badge" style={{ color: latestReadingBand.color, backgroundColor: latestReadingBand.background }}>{latestReadingBand.label}</span><p>{formatDate(readings[0].reading_date)}</p></div><AirQualityMascot value={readings[0].api_value} /></div></section> : null}
      <section className="section"><h2>Zone trend</h2>{readings?.length ? <TrendChart title="Daily API history" points={[...readings].reverse().map((row) => ({ label: row.reading_date.slice(5), value: row.api_value }))} /> : <p className="muted">No readings for this zone yet.</p>}</section>
      <DataTable title="Payment history" rows={(payments ?? []).map((row) => [formatDate(row.created_at?.slice(0, 10)), planNameByPolicyId.get(row.policy_id) ?? "Plan", money(row.amount), row.status])} headings={["Date", "Plan", "Amount", "Status"]} />
      <DataTable title="Payout history" rows={(payouts ?? []).map((row) => {
        const policy = Array.isArray(row.policies) ? row.policies[0] : row.policies;
        const zoneName = zones?.find((zone) => zone.id === policy?.zone_id)?.name ?? "Zone";
        return [formatDate(row.payout_date), zoneName, money(row.amount), row.status];
      })} headings={["Date", "Zone", "Amount", "Status"]} />
      <DataTable title="Recent alerts" rows={(alerts ?? []).map((row) => [new Date(row.created_at).toLocaleString("en-MY"), row.message])} headings={["When", "Message"]} />
    </> : <EmployerDashboard profile={profile} plans={plans ?? []} zones={zones ?? []} policies={policies ?? []} members={members ?? []} />}
  </div>;
}

function EmployerDashboard({ profile, plans, zones, policies, members }: {
  profile: { id: string; company_name: string | null };
  plans: { id: string; name: string; plan_type: string; price: number; description: string }[];
  zones: { id: string; name: string; state: string }[];
  policies: { user_id: string | null; status: string; start_date: string; end_date: string; sponsor_policy_id: string | null }[];
  members: { customer_id: string; status: string; profiles: { name: string; email: string; occupation: string | null } | { name: string; email: string; occupation: string | null }[] | null }[];
}) {
  const today = new Date().toISOString().slice(0, 10);
  const activePolicy = policies.some((policy) => !policy.sponsor_policy_id && policy.status === "active" && policy.start_date <= today && policy.end_date >= today);
  const activeMembers = members.filter((member) => member.status === "active");
  const profileOf = (member: typeof members[number]) => Array.isArray(member.profiles) ? member.profiles[0] : member.profiles;
  const sponsoredCover = policies.filter((policy) => policy.sponsor_policy_id && policy.status === "active" && policy.start_date <= today && policy.end_date >= today).length;
  const coveredMembers = activeMembers.filter((member) => policies.some((policy) => policy.user_id === member.customer_id && policy.sponsor_policy_id && policy.status === "active" && policy.start_date <= today && policy.end_date >= today)).length;
  return <>
    <h2>{profile.company_name ?? "Employer team"}</h2>
    <div className="grid three"><article className="card"><p className="eyebrow">Group cover</p><strong>{activePolicy ? "Active" : "Not active"}</strong></article><article className="card"><p className="eyebrow">Team members</p><strong>{activeMembers.length} / 20</strong></article><article className="card"><p className="eyebrow">Sponsored cover</p><strong>{sponsoredCover}</strong></article></div>
    <section className="section"><BarChart title="Team protection" items={[{ label: "Protected members", value: coveredMembers }, { label: "Not protected", value: activeMembers.length - coveredMembers }]} /></section>
    <section className="section"><h2>Add an existing individual</h2><p className="muted">The person must already have an individual account registered with this Gmail address.</p><form action={addTeamMember} className="form inline-form"><label>Member Gmail address<input type="email" name="email" required placeholder="worker@gmail.com" /></label><button className="button">Add to team</button></form></section>
    <DataTable title="Team roster" headings={["Name", "Gmail", "Occupation", "Membership", "Protection"]} rows={members.map((member) => { const person = profileOf(member); const covered = policies.some((policy) => policy.user_id === member.customer_id && policy.status === "active" && policy.start_date <= today && policy.end_date >= today); return [person?.name ?? "Member", person?.email ?? "—", person?.occupation ?? "—", member.status, covered ? "Protected" : "Not Protected"]; })} />
    <div className="roster-actions">{activeMembers.map((member) => <form action={removeTeamMember} key={member.customer_id}><input type="hidden" name="customer_id" value={member.customer_id} /><button className="button danger secondary">Remove {profileOf(member)?.name ?? "member"}</button></form>)}</div>
    <section className="section"><h2>Employer group plan</h2><p className="muted">Group plan covers up to 20 existing individual accounts.</p><form action={purchasePolicy} className="form inline-form">
      <label>Plan<select name="plan_id">{plans.filter((plan) => plan.plan_type === "group").map((plan) => <option key={plan.id} value={plan.id}>{plan.name} · {money(plan.price)}</option>)}</select></label>
      <label>Work zone<select name="zone_id">{zones.map((zone) => <option value={zone.id} key={zone.id}>{zone.name}, {zone.state}</option>)}</select></label>
      <input type="hidden" name="wallet" value="Touch n Go" /><button className="button" disabled={!activeMembers.length}>Select group plan</button>
    </form></section>
  </>;
}

function DataTable({ title, headings, rows }: { title: string; headings: string[]; rows: (string | number)[][] }) {
  return <section className="section"><h2>{title}</h2>{rows.length ? <div className="table-wrap"><table><thead><tr>{headings.map((heading) => <th key={heading}>{heading}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div> : <p className="muted">Nothing to show yet.</p>}</section>;
}
