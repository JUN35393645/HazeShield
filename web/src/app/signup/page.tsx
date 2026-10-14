import Link from "next/link";
import { AuthForm } from "@/components/auth-form";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function SignupPage({ searchParams }: { searchParams: Promise<{ type?: string }> }) {
  const params = await searchParams;
  const supabase = await createClient();
  const { data: zones, error } = await supabase.from("zones").select("id,name,state").order("name");
  if (error) throw new Error(`Could not load signup zones: ${error.message}`);
  return <section className="auth-card card wide-card">
    <p className="eyebrow">Create an account</p><h1>Get started</h1>
    <AuthForm mode="signup" zones={zones ?? []} initialType={params.type === "employer" ? "employer" : "individual"} />
    <p className="muted">Already registered? <Link href="/login">Sign in</Link></p>
  </section>;
}
