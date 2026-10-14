export function money(value: number | string | null | undefined): string {
  return new Intl.NumberFormat("en-MY", { style: "currency", currency: "MYR" }).format(Number(value ?? 0));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-MY", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}
