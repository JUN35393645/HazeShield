import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "HazeShield",
    short_name: "HazeShield",
    description: "Haze cover information and account dashboard for outdoor workers.",
    start_url: "/",
    display: "standalone",
    background_color: "#f7f8f3",
    theme_color: "#176b52",
    icons: [
      { src: "/stickers/good.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/stickers/good.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
