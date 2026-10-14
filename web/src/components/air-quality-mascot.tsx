import Image from "next/image";
import { getApiBand } from "@/lib/air-quality";

export function AirQualityMascot({ value, size = "regular" }: {
  value: number | null | undefined;
  size?: "regular" | "small";
}) {
  const band = getApiBand(value);
  if (!band.sticker) return null;

  return <Image
    className={`capybara-sticker capybara-${size}`}
    src={`/stickers/${band.sticker}.png`}
    alt={`HazeShield capybara sticker for ${band.label.toLowerCase()} air quality`}
    width={512}
    height={512}
  />;
}
