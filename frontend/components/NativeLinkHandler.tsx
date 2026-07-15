"use client";

import { useEffect } from "react";
import { Capacitor } from "@capacitor/core";
import { openExternal } from "@/lib/native-links";

/**
 * Intercepts clicks on target="_blank" links so they open in the system
 * browser on native instead of navigating the WKWebView away from the app.
 * One listener covers every external link in the app — no per-link changes.
 */
export default function NativeLinkHandler() {
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    const handleClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement)?.closest("a[target='_blank']");
      if (!(anchor instanceof HTMLAnchorElement)) return;
      const href = anchor.href;
      if (!href.startsWith("http")) return;

      e.preventDefault();
      openExternal(href);
    };

    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  return null;
}
