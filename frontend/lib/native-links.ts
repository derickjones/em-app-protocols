"use client";

/**
 * External-link handling for the native shell: the WKWebView has no back
 * button, so navigating it away from the app to an external site strands
 * the user there with no way back. On native, external links open in the
 * system browser sheet instead; on web this is unchanged.
 */

import { Capacitor } from "@capacitor/core";
import { Browser } from "@capacitor/browser";

export async function openExternal(url: string): Promise<void> {
  if (Capacitor.isNativePlatform()) {
    await Browser.open({ url });
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
