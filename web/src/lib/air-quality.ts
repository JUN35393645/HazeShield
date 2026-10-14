export function getApiBand(value: number | null | undefined) {
  if (value == null) return { label: "No reading", color: "#68736e", background: "#eef0ed", sticker: null };
  if (value <= 100) return { label: "Good / moderate", color: "#176b52", background: "#e5f3ed", sticker: "good" };
  if (value <= 150) return { label: "Sensitive groups", color: "#9a6500", background: "#fff2d2", sticker: "moderate" };
  if (value <= 200) return { label: "Unhealthy", color: "#b64d24", background: "#ffebe2", sticker: "bad" };
  return { label: "Very unhealthy", color: "#a52d43", background: "#f9e6eb", sticker: "bad" };
}
