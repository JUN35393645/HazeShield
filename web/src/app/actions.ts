"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireAdmin, requireProfile } from "@/lib/auth";

export type FormState = { error?: string; message?: string };

const occupations = ["Delivery rider", "E-hailing driver", "Food vendor", "Market trader", "Construction worker", "Outdoor service worker", "Other"];

export async function signIn(_: FormState, formData: FormData): Promise<FormState> {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) return { error: "Enter your email and password." };
  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return { error: error.message };
  redirect("/dashboard");
}

export async function signUp(_: FormState, formData: FormData): Promise<FormState> {
  const name = String(formData.get("name") ?? "").trim();
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const password = String(formData.get("password") ?? "");
  const confirmation = String(formData.get("confirmation") ?? "");
  const accountType = String(formData.get("account_type") ?? "individual");
  const zoneId = String(formData.get("zone_id") ?? "");
  const occupation = String(formData.get("occupation") ?? "");
  const occupationOther = String(formData.get("occupation_other") ?? "").trim();
  const companyName = String(formData.get("company_name") ?? "").trim();
  if (name.length < 2 || name.length > 80 || !email || email.length > 254 || !zoneId) {
    return { error: "Enter a name (2–80 characters), Gmail address, and primary zone." };
  }
  if (password.length < 8) return { error: "Password must be at least 8 characters." };
  if (password !== confirmation) return { error: "The passwords do not match." };
  if (!/^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@gmail\.com$/i.test(email)) {
    return { error: "Use a Gmail address ending in @gmail.com." };
  }
  if (!["individual", "employer"].includes(accountType)) return { error: "Choose a valid account type." };
  if (accountType === "individual" && (!occupations.includes(occupation) || (occupation === "Other" && !occupationOther) || occupationOther.length > 80)) {
    return { error: "Choose an occupation and describe it if you select Other." };
  }
  const supabase = await createClient();
  const { data: zone, error: zoneError } = await supabase.from("zones").select("id").eq("id", zoneId).maybeSingle();
  if (zoneError) return { error: `Could not validate zone: ${zoneError.message}` };
  if (!zone) return { error: "Choose a valid primary zone." };
  if (accountType === "employer" && (!companyName || companyName.length > 120)) {
    return { error: "Enter a business name (1–120 characters)." };
  }
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { name, account_type: accountType, zone_id: zoneId, occupation: occupation || null,
        occupation_other: occupationOther || null, company_name: companyName || null },
    },
  });
  if (error) return { error: error.message };
  if (data.session) redirect("/dashboard");
  redirect("/login?registered=1");
}

export async function signOut() {
  const supabase = await createClient();
  const { error } = await supabase.auth.signOut();
  if (error) throw new Error(`Could not sign out: ${error.message}`);
  redirect("/");
}

export async function purchasePolicy(formData: FormData) {
  const profile = await requireProfile();
  const supabase = await createClient();
  const planId = String(formData.get("plan_id") ?? "");
  const zoneId = String(formData.get("zone_id") ?? "");
  const wallet = String(formData.get("wallet") ?? "");
  const { error } = await supabase.rpc("purchase_policy", {
    p_plan_id: planId, p_zone_id: zoneId, p_wallet: wallet,
  });
  if (error) redirect(`/dashboard?error=${encodeURIComponent(error.message)}`);
  revalidatePath("/dashboard");
  redirect(profile.role === "employer" ? "/dashboard?success=Group%20plan%20recorded" : "/dashboard?success=Plan%20selection%20recorded");
}

export async function addTeamMember(formData: FormData) {
  const profile = await requireProfile();
  if (profile.role !== "employer") redirect("/dashboard");
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!email) redirect("/dashboard?error=Enter%20the%20member%20email");
  const admin = createAdminClient();
  const { data, error } = await admin.from("profiles").select("id,role,account_status").eq("email", email).maybeSingle();
  if (error) throw new Error(`Could not look up account: ${error.message}`);
  if (!data || data.role !== "customer" || data.account_status !== "active") redirect("/dashboard?error=No%20existing%20individual%20account%20has%20that%20Gmail%20address");
  const { data: result, error: rpcError } = await (await createClient()).rpc("add_employer_member", {
    p_customer_id: data.id,
  });
  if (rpcError) redirect(`/dashboard?error=${encodeURIComponent(rpcError.message)}`);
  void result;
  revalidatePath("/dashboard");
  redirect("/dashboard?success=Team%20member%20added");
}

export async function removeTeamMember(formData: FormData) {
  const profile = await requireProfile();
  if (profile.role !== "employer") redirect("/dashboard");
  const supabase = await createClient();
  const { error } = await supabase.rpc("remove_employer_member", {
    p_customer_id: String(formData.get("customer_id") ?? ""),
  });
  if (error) redirect(`/dashboard?error=${encodeURIComponent(error.message)}`);
  revalidatePath("/dashboard");
  redirect("/dashboard?success=Member%20removed%20and%20sponsored%20cover%20cancelled");
}

export async function updatePolicyStatus(formData: FormData) {
  await requireAdmin();
  const supabase = await createClient();
  const { error } = await supabase.rpc("admin_set_policy_status", {
    p_policy_id: String(formData.get("policy_id") ?? ""),
    p_status: String(formData.get("status") ?? ""),
  });
  if (error) redirect(`/admin?error=${encodeURIComponent(error.message)}`);
  revalidatePath("/admin");
  redirect("/admin?success=Policy%20status%20updated");
}

export async function recordReading(formData: FormData) {
  await requireAdmin();
  const supabase = await createClient();
  const { error } = await supabase.rpc("admin_record_reading", {
    p_zone_id: String(formData.get("zone_id") ?? ""),
    p_reading_date: String(formData.get("reading_date") ?? ""),
    p_api_value: Number(formData.get("api_value")),
  });
  if (error) redirect(`/admin?error=${encodeURIComponent(error.message)}`);
  revalidatePath("/admin");
  redirect("/admin?success=Reading%20stored%20and%20trigger%20rules%20evaluated");
}

export async function resetDemoActivity(formData: FormData) {
  await requireAdmin();
  if (formData.get("confirm") !== "on") redirect("/admin?error=Confirm%20the%20demo%20activity%20reset");
  const supabase = await createClient();
  const { error } = await supabase.rpc("admin_reset_demo_activity");
  if (error) redirect(`/admin?error=${encodeURIComponent(error.message)}`);
  revalidatePath("/admin");
  revalidatePath("/dashboard");
  redirect("/admin?success=Demo%20activity%20reset;%20accounts%20were%20kept");
}

export async function anonymizeAccount(formData: FormData) {
  await requireAdmin();
  if (formData.get("confirm") !== "on") redirect("/admin?error=Confirm%20account%20anonymization");
  const userId = String(formData.get("user_id") ?? "");
  const supabase = await createClient();
  const { error } = await supabase.rpc("admin_anonymize_account", { p_user_id: userId });
  if (error) redirect(`/admin?error=${encodeURIComponent(error.message)}`);
  const admin = createAdminClient();
  const { error: authError } = await admin.auth.admin.deleteUser(userId, false);
  if (authError) throw new Error(`Account data was anonymized, but sign-in deletion failed: ${authError.message}`);
  revalidatePath("/admin");
  redirect("/admin?success=Account%20anonymized%20and%20sign-in%20removed");
}
