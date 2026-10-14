"use client";

import { useEffect } from "react";

export function OfflineRegistration() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((error: unknown) => {
        console.error("HazeShield service worker registration failed.", error);
      });
    }
  }, []);
  return null;
}
