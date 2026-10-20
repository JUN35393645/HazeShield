export function getApiBand(value: number | null | undefined) {
  if (value == null) return { label: "No reading", color: "#68736e", background: "#eef0ed", sticker: null };
  if (value <= 100) return { label: "Good / moderate", color: "#176b52", background: "#e5f3ed", sticker: "good" };
  if (value <= 150) return { label: "Sensitive groups", color: "#9a6500", background: "#fff2d2", sticker: "moderate" };
  if (value <= 200) return { label: "Unhealthy", color: "#b64d24", background: "#ffebe2", sticker: "bad" };
  return { label: "Very unhealthy", color: "#a52d43", background: "#f9e6eb", sticker: "bad" };
}

export function getRecentDateRange(dayCount: number): string[] {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kuala_Lumpur",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) => parts.find((item) => item.type === type)?.value;
  const today = `${part("year")}-${part("month")}-${part("day")}`;
  const end = new Date(`${today}T00:00:00Z`);
  return Array.from({ length: dayCount }, (_, index) => {
    const date = new Date(end);
    date.setUTCDate(end.getUTCDate() - dayCount + index + 1);
    return date.toISOString().slice(0, 10);
  });
}

export function fillDailyReadings(
  readings: { reading_date: string; api_value: number }[],
  dates: string[],
): { label: string; value: number | null }[] {
  const valuesByDate = new Map(readings.map((reading) => [reading.reading_date, reading.api_value]));
  return dates.map((date) => ({ label: date.slice(5), value: valuesByDate.get(date) ?? null }));
}
