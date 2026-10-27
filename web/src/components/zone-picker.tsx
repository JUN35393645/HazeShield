"use client";

import { useRouter } from "next/navigation";

export function ZonePicker({ zones, selectedZoneId }: {
  zones: { id: string; name: string; state: string }[];
  selectedZoneId?: string;
}) {
  const router = useRouter();

  return <div className="form zone-picker">
    <label htmlFor="zone">Choose a zone</label>
    <select
      id="zone"
      name="zone"
      value={selectedZoneId ?? ""}
      onChange={(event) => {
        const searchParams = new URLSearchParams(window.location.search);
        searchParams.set("zone", event.currentTarget.value);
        router.replace(`/?${searchParams.toString()}`, { scroll: false });
      }}
    >
      {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name} · {zone.state}</option>)}
    </select>
  </div>;
}
