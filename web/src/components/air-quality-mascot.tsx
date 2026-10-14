import Image from "next/image";

export function AirQualityMascot({ value, size = "regular" }: {
  value: number | null | undefined;
  size?: "regular" | "small";
}) {
  if (value == null) return null;
  const mood = value <= 100 ? "good" : value <= 150 ? "moderate" : "bad";
  const description = mood === "good" ? "good" : mood === "moderate" ? "moderate" : "poor";

  return <Image
    className={`capybara-sticker capybara-${size}`}
    src={`/stickers/${mood}.png`}
    alt={`HazeShield capybara sticker for ${description} air quality`}
    width={512}
    height={512}
  />;
}
