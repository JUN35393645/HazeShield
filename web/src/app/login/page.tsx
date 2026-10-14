import Link from "next/link";
import { AuthForm } from "@/components/auth-form";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ registered?: string }> }) {
  const params = await searchParams;
  return <section className="auth-card card">
    <p className="eyebrow">Welcome back</p><h1>Sign in</h1>
    {params.registered && <p className="notice">Account created. Sign in with the email and password you registered.</p>}
    <AuthForm mode="login" />
    <p className="muted">New to HazeShield? <Link href="/signup">Create an account</Link></p>
  </section>;
}
