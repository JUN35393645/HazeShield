import { requireAdmin } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import { formatDate, money } from "@/lib/format";
import { anonymizeAccount, recordReading, resetDemoActivity, signOut, updatePolicyStatus } from "@/app/actions";
import { BarChart } from "@/components/trend-chart";

export const dynamic = "force-dynamic";

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ error?: string; success?: string }> }) {
  await requireAdmin();
  const params = await searchParams;
  const supabase = await createClient();
  const [{ data: accounts, error: accountError }, { data: policies, error: policyError },
    { data: zones, error: zoneError },
    { data: readings, error: readingError }, { data: audit, error: auditError },
    { data: payments, error: paymentError }, { data: payouts, error: payoutError }] = await Promise.all([
    supabase.from("profiles").select("id,name,email,role,zone_id,account_status").eq("account_status", "active").order("name"),
    supabase.from("policies").select("id,user_id,status,start_date,end_date,plans(name),profiles!policies_user_id_fkey(name)").order("created_at", { ascending: false }),
    supabase.from("zones").select("id,name,state").order("name"),
    supabase.from("readings").select("reading_date,api_value,source,zone_id,zones(name)").order("reading_date", { ascending: false }).limit(100),
    supabase.from("audit_logs").select("action,details,created_at").order("created_at", { ascending: false }).limit(100),
    supabase.from("payments").select("amount,status"),
    supabase.from("payouts").select("amount,status"),
  ]);
  const errors = [accountError, policyError, zoneError, readingError, auditError, paymentError, payoutError].filter(Boolean);
  if (errors.length) throw new Error(`Could not load admin console: ${errors[0]?.message}`);
  const active = (policies ?? []).filter((item) => item.status === "active" && item.start_date <= new Date().toISOString().slice(0, 10) && item.end_date >= new Date().toISOString().slice(0, 10));
  const byRole = (accounts ?? []).filter((account) => account.role !== "admin");
  const accountMix = ["customer", "employer"].map((role) => ({
    label: role === "customer" ? "Customers" : "Employers",
    value: byRole.filter((account) => account.role === role).length,
  }));
  const accountsByZone = (zones ?? []).map((zone) => ({
    label: zone.name,
    value: byRole.filter((account) => account.zone_id === zone.id).length,
  })).filter((item) => item.value > 0);
  const policiesByPlan = new Map<string, number>();
  (policies ?? []).forEach((policy) => {
    const plan = Array.isArray(policy.plans) ? policy.plans[0] : policy.plans;
    const label = `${plan?.name ?? "Unknown plan"} · ${policy.status}`;
    policiesByPlan.set(label, (policiesByPlan.get(label) ?? 0) + 1);
  });
  const latestByZone = new Map<string, number>();
  (readings ?? []).forEach((reading) => {
    if (!latestByZone.has(reading.zone_id)) latestByZone.set(reading.zone_id, reading.api_value);
  });
  return <div className="page-shell section">
    <div className="page-heading"><div><p className="eyebrow">Restricted operations area</p><h1>HazeShield admin</h1></div><form action={signOut}><button className="button secondary">Sign out</button></form></div>
    {params.error && <p className="error notice">{params.error}</p>}{params.success && <p className="notice">{params.success}</p>}
    <div className="grid four">
      <article className="card"><p className="eyebrow">Active policies</p><strong>{active.length}</strong></article>
      <article className="card"><p className="eyebrow">Premium records</p><strong>{money((payments ?? []).filter((x) => x.status === "paid").reduce((sum, x) => sum + Number(x.amount), 0))}</strong></article>
      <article className="card"><p className="eyebrow">Payout records</p><strong>{money((payouts ?? []).filter((x) => x.status === "paid").reduce((sum, x) => sum + Number(x.amount), 0))}</strong></article>
      <article className="card"><p className="eyebrow">Accounts</p><strong>{byRole.length}</strong></article>
    </div>
    <p className="muted">All payment and payout figures are records only; no funds are transferred.</p>
    <section className="section"><h2>Activity at a glance</h2><div className="grid two">
      <BarChart title="Accounts by zone" items={accountsByZone} />
      <BarChart title="Account types" items={accountMix} />
      <BarChart title="Policies by plan and status" items={[...policiesByPlan].map(([label, value]) => ({ label, value }))} />
      <BarChart title="Latest API by zone" highlightAbove={150} items={(zones ?? []).flatMap((zone) => {
        const value = latestByZone.get(zone.id);
        return value === undefined ? [] : [{ label: zone.name, value }];
      })} />
    </div></section>
    <section className="section"><h2>Accounts and policies</h2>{byRole.length ? <div className="table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Zone</th><th>Protection</th><th>Remove</th></tr></thead><tbody>{byRole.map((account) => {
      const zone = zones?.find((item) => item.id === account.zone_id);
      return <tr key={account.id}><td>{account.name}</td><td>{account.email}</td><td>{account.role}</td><td>{zone?.name ?? "—"}</td><td>{policies?.some((item) => item.user_id === account.id && item.status === "active") ? "Active" : "—"}</td><td><form action={anonymizeAccount} className="confirm-form"><input type="hidden" name="user_id" value={account.id} /><label><input type="checkbox" name="confirm" required /> Confirm</label><button className="button danger secondary">Anonymize</button></form></td></tr>;
    })}</tbody></table></div> : <p className="muted">No customer or employer accounts.</p>}
    <h3>Change policy status</h3><form action={updatePolicyStatus} className="form inline-form"><label>Policy<select name="policy_id">{policies?.map((policy) => <option key={policy.id} value={policy.id}>#{policy.id.slice(0, 8)} · {(policy.profiles as { name?: string } | null)?.name ?? "Account"} · {(policy.plans as { name?: string } | null)?.name} · {policy.status}</option>)}</select></label><label>Status<select name="status"><option value="active">Active</option><option value="cancelled">Cancelled</option></select></label><button className="button" disabled={!policies?.length}>Save status</button></form></section>
    <section className="section"><h2>Manual trigger tools</h2><p className="notice">Manual readings are evaluated for the demo trigger. No payout is transferred.</p><form action={recordReading} className="form inline-form"><label>Zone<select name="zone_id">{zones?.map((zone) => <option value={zone.id} key={zone.id}>{zone.name}</option>)}</select></label><label>Reading date<input type="date" name="reading_date" defaultValue={new Date().toISOString().slice(0, 10)} required /></label><label>API value<input type="number" name="api_value" min="0" max="1000" defaultValue="160" required /></label><button className="button">Store reading and evaluate</button></form></section>
    <section className="section"><h2>Zone readings</h2><DataTable headings={["Zone", "Date", "API", "Source"]} rows={(readings ?? []).map((row) => [(row.zones as { name?: string } | null)?.name ?? "—", formatDate(row.reading_date), row.api_value, row.source])} /></section>
    <section className="section"><h2>Audit log</h2><DataTable headings={["When", "Action", "Details"]} rows={(audit ?? []).map((row) => [new Date(row.created_at).toLocaleString("en-MY"), row.action, row.details])} /></section>
    <section className="section"><h2>Reset demo activity</h2><p className="error">This clears all policies, payments, payouts, trigger events, team rosters, notifications, and readings. Accounts are retained.</p><form action={resetDemoActivity} className="form"><label className="check-label"><input type="checkbox" name="confirm" required /> I understand this clears demo activity for all accounts.</label><button className="button danger secondary">Reset demo activity</button></form></section>
  </div>;
}

function DataTable({ headings, rows }: { headings: string[]; rows: (string | number)[][] }) {
  return rows.length ? <div className="table-wrap"><table><thead><tr>{headings.map((heading) => <th key={heading}>{heading}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, col) => <td key={col}>{cell}</td>)}</tr>)}</tbody></table></div> : <p className="muted">Nothing to show.</p>;
}
