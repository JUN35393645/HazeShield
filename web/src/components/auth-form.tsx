"use client";

import { useActionState } from "react";
import { useState } from "react";
import { signIn, signUp, type FormState } from "@/app/actions";

const occupations = ["Delivery rider", "E-hailing driver", "Food vendor", "Market trader", "Construction worker", "Outdoor service worker", "Other"];

export function AuthForm({ mode, zones = [], initialType = "individual" }: {
  mode: "login" | "signup";
  zones?: { id: string; name: string; state: string }[];
  initialType?: string;
}) {
  const action = mode === "login" ? signIn : signUp;
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const [accountType, setAccountType] = useState(initialType);
  return <form action={formAction} className="form">
    {mode === "signup" && <>
      <label>Account type<select name="account_type" value={accountType} onChange={(event) => setAccountType(event.target.value)}><option value="individual">Individual</option><option value="employer">Employer</option></select></label>
      <label>Full name<input name="name" required minLength={2} maxLength={80} autoComplete="name" /></label>
    </>}
    <label>Gmail address<input name="email" type="email" required autoComplete="email" placeholder="you@gmail.com" /></label>
    <label>Password<input name="password" type="password" required minLength={mode === "signup" ? 8 : 1} autoComplete={mode === "signup" ? "new-password" : "current-password"} /></label>
    {mode === "signup" && <>
      <label>Confirm password<input name="confirmation" type="password" required minLength={8} autoComplete="new-password" /></label>
      <label>Primary zone<select name="zone_id" required defaultValue=""><option value="" disabled>Select a zone</option>{zones.map((zone) => <option value={zone.id} key={zone.id}>{zone.name}, {zone.state}</option>)}</select></label>
      {accountType === "individual" ? <>
        <label>Occupation<select name="occupation" defaultValue="" required><option value="" disabled>Select occupation</option>{occupations.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Occupation description (if Other)<input name="occupation_other" maxLength={80} /></label>
      </> : <label>Business name<input name="company_name" maxLength={120} required /></label>}
      <p className="muted form-hint">Use a Gmail-format address and a password with at least 8 characters.</p>
    </>}
    {state.error && <p className="error" role="alert">{state.error}</p>}
    <button className="button" disabled={pending}>{pending ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
  </form>;
}
