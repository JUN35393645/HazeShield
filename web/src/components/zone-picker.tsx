"use client";

export function ZonePicker({ zones, selectedZoneId }: {
  zones: { id: string; name: string; state: string }[];
  selectedZoneId?: string;
}) {
  return <form action="/" method="get" className="form zone-picker">
    <label htmlFor="zone">Choose a zone</label>
    <select id="zone" name="zone" value={selectedZoneId ?? ""} onChange={(event) => event.currentTarget.form?.requestSubmit()}>
      {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name} · {zone.state}</option>)}
    </select>
  </form>;
}
