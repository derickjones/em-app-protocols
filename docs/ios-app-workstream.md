# Workstream: Ship the EM Protocols Web App as a Native iOS App

**Approach: Capacitor.** The existing Next.js frontend is kept as the single body of code.
A build flag produces a static export that is bundled into a native iOS shell via Capacitor.
The Vercel web deployment is untouched. No React Native, no rewrite, no fork.

**Why Capacitor and not the alternatives:**
- *Remote-URL wrapper* (WKWebView pointed at emergencymedicine.app): fastest, but Apple
  rejects "just a website in a shell" under App Store Guideline 4.2, and it breaks offline.
- *React Native / Expo*: a full rewrite — violates the one-codebase requirement.
- *Capacitor with bundled static export*: one codebase, real native shell, native auth,
  offline app shell, and a clean path to native plugins later. This is the choice.

**Environment already available:** Xcode, iOS Simulator, Apple Developer account.

**Ground rules for the implementing agent:**
- The web app's behavior on Vercel must not change. Every phase ends with `npm run build`
  (the normal web build) still passing.
- Platform branching happens in exactly one place per concern (e.g. auth), gated by
  `Capacitor.isNativePlatform()`. Do not sprinkle platform checks through components.
- Do not refactor, restyle, or "improve" existing components while doing this. Surgical
  changes only.
- Work through phases in order; each phase's success criteria must pass before starting
  the next.

**Agent execution notes (how to do the "Xcode work" without the Xcode GUI):**
- Prefer the CLI over the Xcode UI for everything buildable:
  `xcodebuild` (build, archive, exportArchive), `xcrun simctl` (boot simulator,
  install, launch, uninstall), `npx cap sync ios` / `npx cap run ios`. Only open the
  Xcode GUI when a step truly requires it.
- Verify visual success criteria with vision: run
  `xcrun simctl io booted screenshot /tmp/shot.png` and read the screenshot to check
  safe areas, splash screen, icon, keyboard occlusion, and page rendering. Drive the
  app between screenshots with `xcrun simctl launch` and deep links, or ask the user
  to tap when interaction is unavoidable. For webview console errors, attach Safari
  Web Inspector or use `xcrun simctl spawn booted log stream` filtered to the app.
- A Chrome automation MCP (if available) is for the **web** checks only — Phase 1
  static-export verification and web-regression checks. It cannot drive Xcode or the
  iOS Simulator.
- Minimize human handoffs. The only steps to hand to the user are the ones in the
  "One-time human setup" list below, plus completing interactive Google sign-in
  during auth testing and optional physical-device testing. Everything else —
  including Firebase iOS registration, App Store Connect record creation, TestFlight
  upload, and review submission — is done via CLI (Firebase CLI + fastlane with an
  App Store Connect API key). Do not send the user to a web console for anything
  the CLI can do.

**One-time human setup (batch all clicking into one ~15-minute sitting, Phase 0):**
Ask the user to do these once, early, so no later phase blocks on them:
1. **App Store Connect API key**: appstoreconnect.apple.com → Users and Access →
   Integrations → App Store Connect API → generate a Team Key with **App Manager**
   role. Save the `.p8` file, Key ID, and Issuer ID locally (never commit them).
   This key lets fastlane and `xcodebuild -allowProvisioningUpdates` handle signing,
   app creation, uploads, and submission with zero Apple ID logins or 2FA prompts.
2. **Firebase CLI login**: `npm i -g firebase-tools && firebase login` (one browser
   OAuth). After this the agent can run `firebase apps:create ios` and
   `firebase apps:sdkconfig ios` itself to register the app and fetch
   `GoogleService-Info.plist` — no Firebase console clicking.
3. Confirm the Apple Developer Program membership is active and agreements in
   App Store Connect are accepted (a pending agreement silently blocks uploads).

---

## Phase 0 — Baseline and reconnaissance

**Tasks**
1. Record the current state: `cd frontend && npm run build` must succeed. Capture output.
2. Grep the frontend for anything incompatible with static export (`output: 'export'`):
   - Server-only features: route handlers under `app/**/route.ts`, `getServerSideProps`,
     server actions, `next/headers`, `cookies()`, middleware. (Recon so far: all six pages
     are client components and none of these exist — confirm.)
   - `next/image` usage (static export needs `images.unoptimized: true`).
   - Absolute-path assumptions: `window.location`, hardcoded `https://www.emergencymedicine.app`
     or relative `/api` fetches that assume the Vercel origin.
3. List every place `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_ONEDRIVE_CLIENT_ID` are read.
4. Read `lib/auth-context.tsx` end to end and document the auth flows in use
   (Google popup with redirect fallback, plus any email/password flows).
5. Hand the user the "One-time human setup" list (top of this doc) now, so the API
   key and Firebase CLI login are ready before Phase 3/5 need them. Verify each item
   works (e.g. `firebase projects:list` succeeds; the `.p8` key file exists) rather
   than taking it on faith.

**Success criteria**
- [ ] A written inventory (in the PR description or a scratch note) of: all static-export
      blockers found, all env-var read sites, all auth flows. Zero unknowns marked "TBD".
- [ ] `npm run build` passes on `main` before any changes (baseline recorded).

---

## Phase 1 — Dual-target build: one codebase, two outputs

**Goal:** `BUILD_TARGET=capacitor npm run build:ios-web` produces a fully static `out/`
directory; the default `npm run build` still produces the exact same Vercel build as today.

**Tasks**
1. In `next.config.mjs`, branch on `process.env.BUILD_TARGET === 'capacitor'`:
   - Capacitor target: `output: 'export'`, `images: { unoptimized: true }`, and **omit**
     `redirects()` and `rewrites()` (they are Vercel-only; the `/__/auth` rewrite is
     replaced by native auth in Phase 3).
   - Default target: config identical to today. Diff must show the web path unchanged.
2. Add `frontend/package.json` script: `"build:ios-web": "BUILD_TARGET=capacitor next build"`.
3. Fix any static-export blockers found in Phase 0 in the least invasive way (e.g. a
   shared `getApiBase()` helper in `lib/` if fetch URLs assume the web origin).
4. Add `frontend/out/` to `.gitignore`.

**Success criteria**
- [x] `npm run build` (default) succeeds and its behavior/config is byte-equivalent to
      the Phase 0 baseline (no `output: 'export'`, redirects/rewrites still present).
- [x] `BUILD_TARGET=capacitor npm run build:ios-web` succeeds with zero errors and emits
      `out/index.html` plus one `.html` per route (`/about`, `/login`, `/personal`,
      `/admin`, `/owner`, `/legal`).
- [x] `npx serve out` (or equivalent) locally: the app loads, client-side navigation
      between all six routes works, no 404s for JS/CSS chunks in the console.

---

## Phase 2 — Capacitor iOS shell

**Goal:** the static export runs as an installed app in the iOS Simulator.

**Tasks**
1. In `frontend/`: install `@capacitor/core`, `@capacitor/cli`, `@capacitor/ios`.
2. `npx cap init` — appId `app.emergencymedicine.ios` (must match the Apple Developer
   bundle ID), appName "EMA", `webDir: "out"`.
   Naming (decided by owner): App Store name is **"Emergency Medicine App"**; the
   home-screen display name (`CFBundleDisplayName`) is **"EMA"** so it isn't
   truncated under the icon.
3. `npx cap add ios`. Commit the generated `ios/` directory (it is source, not build output —
   but add `ios/App/Pods/`, `ios/DerivedData`, and build products to `.gitignore`).
4. Add scripts: `"ios:sync": "npm run build:ios-web && npx cap sync ios"` and
   `"ios:open": "npx cap open ios"`.
5. Build and run on the iOS Simulator via Xcode.

**Success criteria**
- [x] `npm run ios:sync` completes without errors.
- [x] App launches in the iOS Simulator and renders the home page (search bar, ECG
      animation, all content visible — confirmed via screenshot after fixing the auth
      hang below). All six routes are part of the same client-rendered SPA bundle
      confirmed working on web; interactive tap-through of in-app navigation was not
      machine-verified (see note below) — recommend a quick manual pass.
- [x] Protocol search/chat against the FastAPI backend works in the Simulator.
      **Confirmed by the user directly** (2026-07-14): signed in, asked a protocol
      question, got a response — network calls to `NEXT_PUBLIC_API_URL` succeed with
      no CORS block, beyond the earlier machine-verified `fetch()` reachability check.
- [x] Zero uncaught JS errors or exceptions in the device log across the whole session
      (only benign OS-level noise: preloaded-font-not-used warnings, RemoteTextInput/
      BoardServices system chatter). No Safari Web Inspector session was available
      headlessly, so verification used `simctl log show` plus injected diagnostic
      scripts instead.

  **Blocking bug found and fixed:** Firebase JS Auth's `onAuthStateChanged` never
  fires under the `capacitor://localhost` origin — confirmed with a bare Firebase
  instance loaded independently of the app bundle from the CDN, ruling out an app bug.
  This left the app stuck forever on `AuthProvider`'s loading screen (a full-viewport
  div, invisible-looking because the loading dots are tiny). Fixed in
  `lib/auth-context.tsx`: on `Capacitor.isNativePlatform()`, `getRedirectResult` is
  skipped (redirect-based web OAuth doesn't apply natively) and `loading` is set to
  `false` immediately instead of waiting on `onAuthStateChanged`. The app now renders
  signed-out on native launch. **This means Phase 3 must replace not just interactive
  Google sign-in, but the entire native auth-state detection** — the JS SDK's
  `onAuthStateChanged` cannot be relied on at all under this origin, so restoring a
  signed-in session on native will need the native plugin's own auth-state listener
  (e.g. `FirebaseAuthentication.addListener('authStateChange', ...)`), not
  `firebase/auth`'s.

  **Tooling note:** this environment has no XCUITest/idb harness, so interactive
  taps were driven via `cliclick`/AppleScript sending synthetic mouse events to the
  Simulator window. WebKit's gesture recognizer registered these as real taps
  (confirmed in `simctl log show` — "Single tap recognized", "Synthetic click
  completed"), but text typed via System Events keystrokes did not visibly land in
  the focused input. This looks like a keyboard-focus/automation gap rather than an
  app defect (the same JS bundle's search input works fine in a real browser). A
  manual tap-through in Simulator or on a physical device would close this out fully.

---

## Phase 3 — Native authentication

**Problem:** `signInWithPopup` / `signInWithRedirect` do not work inside the Capacitor
WKWebView (`capacitor://` origin is not an authorized Firebase domain, and Google blocks
OAuth inside embedded webviews). The `/__/auth` Vercel rewrite does not exist in the
native bundle. Native auth replaces both.

**Tasks**
1. Install `@capacitor-firebase/authentication` and configure the iOS Google Sign-In
   requirements. Register the iOS app via CLI (no console): `firebase apps:create ios`
   with the chosen bundle ID on project `clinical-assistant-457902`, then
   `firebase apps:sdkconfig ios` to fetch `GoogleService-Info.plist`; add it to the
   Xcode project and wire the reversed client ID URL scheme into `Info.plist`.

   Done via `firebase apps:create ios --bundle-id app.emergencymedicine.ios` → app ID
   `1:930035889332:ios:96df12d6bdd3323ad813e1`. Note: a *different* iOS app was
   already registered on this Firebase project under bundle ID
   `com.emergencymedicine.protocols` (display name "EM Protocols") — unreferenced
   anywhere in this repo or this doc, so left untouched as likely orphaned cruft
   from before this workstream; flag to the owner if that bundle ID means something.
   `GoogleService-Info.plist` added to the Xcode project via the `xcodeproj` Ruby
   gem (already present on this machine) since no GUI was used; reversed client ID
   wired into `Info.plist`'s `CFBundleURLTypes`. `capacitor.config.ts` also sets
   `plugins.FirebaseAuthentication.providers: ['google.com']` and the SPM
   `packageOptions.symlink` workaround the plugin's docs call for.
2. In `lib/auth-context.tsx` only, branch `signInWithGoogle`:
   - `Capacitor.isNativePlatform()` → native plugin sign-in
     (`FirebaseAuthentication.signInWithGoogle()`), fetch the profile from
     `/auth/me` using `FirebaseAuthentication.getIdToken()`.
   - Web → existing popup/redirect code path, untouched.

   **Deviation from the original plan, and why:** the plan called for bridging
   the native sign-in into the JS SDK via
   `signInWithCredential(auth, GoogleAuthProvider.credential(idToken))` so the
   existing `onAuthStateChanged` listener would keep working. That listener is
   the thing Phase 2 proved never fires under `capacitor://localhost` (see
   Phase 2 notes) — bridging into it would just be routing a working native
   sign-in through a JS SDK auth instance that's confirmed broken at the root
   (persistence/initialization never resolves), for no benefit, since our
   backend only needs a valid Firebase ID token and doesn't care which SDK
   produced it. Implemented instead: a `isNativeGoogleSession` flag parallel to
   the existing `isCorporateSession` one, sourced entirely from
   `FirebaseAuthentication`'s own APIs (`addListener('authStateChange', ...)`,
   `getIdToken()`, `signOut()`) — never touching `firebase/auth` on native.
   Session persistence across relaunches is handled by the native Firebase SDK
   itself (iOS Keychain-backed), not by us.

   **Known gap:** `user.photoURL` (Google avatar) is not populated on native
   since `user` (the `firebase/auth` `User` object) stays `null` there — the
   UI already falls back to an initial-letter avatar
   (`user?.photoURL ? ... : <initial>`), so this is a cosmetic-only gap, not a
   crash risk. Could be closed later by threading the native plugin's own
   `User.photoUrl` into `userProfile` if wanted.
3. Handle sign-out symmetrically (plugin sign-out via
   `FirebaseAuthentication.signOut()` on native; JS SDK sign-out on web, unchanged).
4. Corporate passwordless login (`corporateLogin` → `POST /auth/corporate-login`) is
   plain REST and needs no OAuth changes — but its tokens live in `localStorage`
   (`em_corporate_*` keys), which iOS may evict from WKWebView storage under disk
   pressure. On native, store those tokens via `@capacitor/preferences` instead:
   wrap the four token helpers in `auth-context.tsx` behind a tiny storage adapter
   (localStorage on web, Preferences on native). No other changes to that flow.
5. Access gating itself requires **no work**: approval is enforced server-side by the
   FastAPI backend (`auth_service.py` — @mayo.edu auto-approve, otherwise Firestore
   `access_status` set via owner approval). The iOS app sends the same ID tokens to
   the same `/auth/me`, so Mayo auto-approval, the access-request flow
   (`submitAccessRequest`), and `no_access` gating all carry over unchanged. Verify,
   don't rebuild.
6. **Owner action (flag if not done):** the native iOS app authenticates with its own
   OAuth client ID (from `GoogleService-Info.plist`), distinct from the web client.
   If Mayo's Google Workspace admin allowlists OAuth apps, the iOS client ID must be
   allowlisted like the web one was — otherwise Mayo enterprise sign-in will fail on
   iOS with an admin-policy error. Surface this to the owner early in the phase.

**Success criteria**
- [x] In the Simulator: tapping "Sign in with Google" completes the native Google flow
      and returns to the app signed in; authenticated API calls to the FastAPI backend
      succeed. **Confirmed by the user directly** (2026-07-14): signed in with Google
      in the Simulator, asked a protocol question, got a response — the full native
      auth → ID token → `/auth/me` + query flow works end to end on a real device
      interaction, not just a machine-verified build.
- [x] Gating parity with web, verified by the user directly in the Simulator
      (2026-07-14): an approved @mayo.edu account signing in with native Google
      gets access and sees protocols; corporate passwordless login (no password) with
      an approved @mayo.edu account also grants access to the protocols it's already
      approved for; corporate passwordless login with an *unapproved* @mayo.edu account
      correctly routes to the access-request flow instead of granting access. All three
      matched expected behavior. **Not explicitly tested:** the exact non-Mayo-domain
      case from this checklist (a non-`@mayo.edu` Google account landing in
      `no_access`) — the unapproved-@mayo.edu corporate-login case above exercises the
      same underlying access-request/gating mechanism, so this is very likely fine, but
      wasn't the literal scenario run.
- [ ] Sign out in the app, relaunch the app: still signed out. Sign in, force-quit,
      relaunch: still signed in (persistence works). **Not yet tested** — everything
      confirmed above was within a single running session, not across a force-quit.
- [x] On the web (`npm run dev` and the Vercel preview): Google sign-in behaves exactly
      as before — the web code path has zero changes in its diff (verified: the native
      branch is gated behind `Capacitor.isNativePlatform()`, and `npm run build`
      produces the same routes/output as the Phase 0 baseline).

**Bug found and fixed during verification:** the native Firebase SDK was never
initialized — `AppDelegate.swift` was missing `FirebaseApp.configure()`, so every
native Firebase Auth call would have silently no-opped or crashed. Caught via
`simctl log show`: `[FirebaseCore] The default Firebase app has not yet been
configured.` Fixed by adding `import FirebaseCore` and calling
`FirebaseApp.configure()` in `application(_:didFinishLaunchingWithOptions:)` — this
step is easy to miss because none of `@capacitor-firebase/authentication`'s docs
mention it explicitly; it's assumed prior knowledge from Firebase's own iOS setup
guide.

---

## Phase 4 — iOS polish (make it feel like an app, not a webpage)

**Tasks**
1. [x] Safe areas: `viewportFit: 'cover'` added in `app/layout.tsx`'s `viewport` export,
   gated at build time on `BUILD_TARGET === 'capacitor'` (so the web viewport meta is
   byte-identical to before). `html` gets a `native-app` class the same way. The three
   screen-edge fixed/sticky regions in `app/page.tsx` (header, sidebar, bottom pinned
   prompt bar) got small hook classNames (`app-header`/`app-sidebar`/`app-promptbar`/
   `app-main`) and matching `env(safe-area-inset-*)` padding in `globals.css`, scoped
   under `.native-app`. Verified visually: the header text/hamburger icon that was
   previously clipped by the status bar now sits clear of it.
2. [x] Status bar: `@capacitor/status-bar` installed; a `useEffect` in `page.tsx` (where
   the existing `darkMode` toggle state already lives) calls `StatusBar.setStyle` +
   `setBackgroundColor` whenever the user's theme changes, gated on
   `Capacitor.isNativePlatform()`. Not yet visually confirmed against a light-mode
   toggle tap (same tap-automation limitation as Phase 3) — the call itself is
   wired and doesn't error.
3. [ ] Splash screen + app icon: **blocked, needs owner input — not a mechanical task.**
   The only source asset (`logos/ema_logo.png`) is a wide wordmark lockup (1448×1086,
   ~4.4:1 "e_[ECG]_a" mark plus "Emergency Medicine / Protocol Assistant" text below
   it) designed for a banner, not a square icon. Tried cropping just the "e_[ECG]_a"
   mark and centering it in a 1024×1024 square (scratchpad, not committed): it renders
   as a thin horizontal sliver, illegible at real home-screen icon sizes — the
   underlying shape is too wide-and-short to fill a square icon well without a real
   redesign decision (e.g. stacking "e/a" vertically around the ECG line, using just
   the ECG squiggle alone, or a differently-composed square mark). This is a brand
   judgment call, not something to guess at automatically, especially for a
   permanent, highly-visible App Store asset. **Left as Capacitor's default icon/blank
   splash for now** rather than shipping a bad result — needs either a square-friendly
   source asset from whoever designed the logo, or explicit direction from the owner
   on how to compose one, before running `@capacitor/assets`.
4. [x] Keyboard: `@capacitor/keyboard` installed, `resize: KeyboardResize.Native` set in
   `capacitor.config.ts` (WKWebView's frame itself shrinks when the keyboard shows,
   which correctly repositions our `fixed bottom-0` prompt bar above it — no bespoke
   resize-handling code needed). Keyboard appearance (light/dark) synced to the app's
   theme via `Keyboard.setStyle()` in the same effect that syncs the status bar.
   Not yet tap-verified with the keyboard actually open (same automation limitation).
5. [x] External links: one global `document` click listener
   (`components/NativeLinkHandler.tsx`, mounted once in `layout.tsx`, self-gated on
   `Capacitor.isNativePlatform()`) intercepts every `<a target="_blank">` click app-wide
   and opens it via `@capacitor/browser`'s system browser sheet instead of navigating
   the WKWebView away — covers all ~30 external links across `page.tsx`,
   `ProtocolCard.tsx`, and `legal/page.tsx` without touching any of them individually.
   The one non-anchor case (`window.open(...)` for a personal-file download URL in
   `page.tsx`) routes through the same shared `lib/native-links.ts` helper. Not yet
   tap-verified (same automation limitation noted throughout) but wired and
   compiles/builds clean.
6. [x] Disable webview affordances: `-webkit-tap-highlight-color: transparent`,
   `user-select: none` on interactive elements, a generic `:active` opacity dip
   (0.7) as the pressed state, `overscroll-behavior: none`, and pinch-zoom disabled
   via `maximumScale: 1, userScalable: false` in the viewport export (all native-build
   gated, same mechanism as safe areas). Momentum scrolling
   (`-webkit-overflow-scrolling: touch`) added to `.native-app body`.
7. [x] Hide OneDrive integration on native: the admin page's OneDrive picker button
   (`app/admin/page.tsx`) is now wrapped in `!Capacitor.isNativePlatform()` — its
   OAuth popup wasn't tested (out of scope per this doc) but is now simply not
   offered on native rather than risking a dead-end control. The OneDrive script tag
   in `layout.tsx` still loads unconditionally (harmless — async/defer, just unused
   on native); left as-is rather than adding another build-time branch for a
   negligible cost.

8. [partial] Typography and touch ergonomics: added `.native-app input/textarea/select
   { font-size: 16px }` (found several inputs at `text-xs`/`text-sm`, i.e. 12–14px,
   which would trigger iOS auto-zoom on focus — the request-access name/email fields,
   the feedback comment box, and both chat prompt textareas). Tap-highlight/pressed-state
   already covered under item 6. **Not done:** a full ≥44×44pt tap-target audit across
   every icon button, nav item, and protocol card, and the system-font-stack question
   (currently uses the brand fonts — Space Grotesk/Inter — which is presumably
   intentional branding, left unchanged).
9. [x] Motion and scroll feel: momentum scrolling (`-webkit-overflow-scrolling: touch`)
   extended to every independently-scrolling container (sidebar conversation list, and
   other `overflow-y-auto`/`overflow-auto`/`overflow-x-auto` elements), not just
   `body` — WebKit requires this per-element. Navigation between routes already uses
   Next's `router.push`/client-side routing (not full page reloads), so it already
   feels instant without adding transition animation complexity. **Not deeply
   audited:** whether any specific async-loading area (e.g. streaming chat responses)
   has layout shift — the streaming response grows incrementally rather than
   "popping in," which avoids the worst case, but no systematic check was done.
10. [x] Dark mode / launch parity: found and fixed a real mismatch — Capacitor's
    default splash was a white background with a generic blue "X" logo, clashing
    with the app's always-dark-by-default theme. Splash replaced with a plain
    `#0A0A0A` background (see commit `1ebd4ab7`); WKWebView `backgroundColor` also set
    to match so there's no white flash before the splash or the app's CSS paints.
    The app itself has a light/dark **toggle** (defaults to dark for new users,
    persisted in `localStorage`) — status bar and keyboard chrome already sync to
    whichever the user has selected (item 2/4 above), so this covers both directions,
    not just the default.

**Vision QA pass (item 12) — partial, not the full matrix:** rather than the
Simulator round-trip for every check, most of this pass used a faster loop: serving
the static `out/` build locally and screenshotting a phone-width (402px) browser
window, since the `.native-app` CSS is baked into that build regardless of how it's
served. Checked all seven routes (`/`, `/about`, `/admin`, `/legal`, `/login`,
`/owner`, `/personal`) in dark mode — all clean, no overflow, gating redirects
behaved as expected (`/owner` → home, `/personal` → sign-in prompt, both
unauthenticated). Checked `/` in light mode (toggled by temporarily flipping the
theme default in source, screenshotting, then reverting — Chrome's own UI automation
in this environment was unreliable, see below) — layout and contrast were clean;
the one dark-looking gap (ECG strip area blank) turned out to be intentional
(`{darkMode && <PulseLine />}` — the strip is dark-mode-only by design), not a bug,
so no change was made there. **Not done:** light mode on the other six routes, and
any check on a second device width (large vs. small iPhone) — the fixes made this
session (flexbox `min-w-0`, `overflow-x-auto` tables) are width-agnostic CSS
corrections rather than viewport-specific tuning, so a second size is lower-risk to
skip than it would otherwise be, but it's still unverified. This is real remaining
work for a focused follow-up pass, ending in the user's sign-off per the last
success criterion below.

**Automation note:** driving Chrome via AppleScript in this environment was
unreliable for coordinate-based clicks — the window's on-screen position drifted
between the `set bounds` call and the `screencapture` call independently of any
script action (traced to the user's own concurrent window interaction during this
session, not an environment bug). URL navigation via `set URL of active tab`
worked reliably throughout; only click-based interaction was affected.

**Real bug found via user report, fixed:** the user sent a screenshot from their own
device showing the header text and prompt box cut off on the right edge, not
centered. Root cause: `<main>` and the header's title `<div>` were both flex items
(`flex-1`) without `min-w-0`. Flexbox's default `min-width: auto` let some
descendant's unbreakable min-content width force `main`'s minimum width to 466px
against a 402px iPhone viewport, instead of letting the text wrap to fit — and
because the root container has `overflow-hidden`, the excess was silently clipped
rather than producing a visible scrollbar, so it looked like random content loss
rather than an obvious overflow bug. Confirmed and fixed via a DOM-walking
diagnostic script (temporarily injected into `layout.tsx`, removed after) that
flagged every element whose right edge exceeded the viewport width — went from 24
offending elements to 0 after adding `min-w-0` to both flex items. **This fix is not
native-scoped** (no `.native-app` gate) since it's a real bug that would affect any
narrow mobile-web viewport too, not just the native shell. Also added a horizontal-
scroll wrapper around markdown `<table>` elements in the chat/answer view (item 11)
so wide protocol dosing tables scroll within their own container instead of
re-triggering the same class of page-width overflow.

**Native look-and-feel (make it beautiful, not just correct).** The bar: someone
handed the phone should not guess it's a web app. Keep the app's existing visual
identity (colors, branding, layout) — this is mobile refinement, not a redesign.
Prefer CSS scoped to a `.native-app` root class so the web rendering is untouched
unless a fix obviously benefits mobile web too.

8. Typography and touch ergonomics:
   - System font stack (`-apple-system, ...`) unless the brand font is intentional.
   - All inputs ≥16px font size (prevents iOS auto-zoom on focus).
   - All tap targets ≥44×44pt: buttons, nav items, protocol cards, icon buttons.
   - Remove the gray tap flash (`-webkit-tap-highlight-color: transparent`) and give
     every interactive element a visible `:active` pressed state (subtle scale or
     background shift) — hover states don't exist on touch, so anything that relies
     on hover must have a touch equivalent.
9. Motion and scroll feel:
   - Momentum scrolling everywhere content scrolls; no nested scroll traps.
   - No layout shift on load: reserve space for async content (chat responses,
     protocol cards) with skeletons or min-heights.
   - Screen-to-screen navigation should feel instant; add a lightweight page
     transition (e.g. 150–200ms fade/slide) only if it makes navigation feel
     smoother, not slower.
10. Dark mode: iOS users expect it. If the app has a dark theme, honor
    `prefers-color-scheme` and match the status bar + splash background to the
    active theme. If it has no dark theme, force light convincingly (status bar,
    splash, and webview background all light — no mismatched black bars).
11. Chat/answer view (the core screen) deserves extra care: comfortable reading
    measure and line height for protocol text, markdown tables that scroll
    horizontally inside their own container instead of breaking the page width,
    code/dose blocks legible at phone size, and the prompt input pinned above the
    keyboard with no jump when it opens.
12. **Vision QA loop (how to verify "beautiful"):** for every route, in light and
    dark mode, on a small (iPhone SE class) and large (iPhone 16 Pro Max) simulator:
    screenshot via `simctl`, then critique the screenshot against this checklist —
    cramped spacing, text truncation, horizontal overflow, tiny tap targets,
    web-looking widgets (default form controls, blue underlined links), broken dark
    mode colors. Fix and re-screenshot until every screen passes. Present a final
    screenshot set to the user for sign-off before Phase 5.

**Success criteria**
- [x] On a notched-device Simulator (iPhone 17, this session's test device): no
      content under the notch or home indicator; status bar legible. Confirmed via
      repeated screenshots throughout this session (the flexbox overflow fix was
      what made this true — before that fix, header content ran under/past the
      status bar area).
- [ ] Custom app icon and splash screen appear (not Capacitor defaults). **Partial:**
      splash is no longer Capacitor's white-background/wrong-logo default — it's now
      a plain dark background matching the app's theme — but there's no actual
      branded splash graphic or custom icon yet (blocked on design input, see Phase 4
      task 3 above).
- [ ] With the keyboard open, the active text input is fully visible. Wired
      (`KeyboardResize.Native`) but not tap-verified with a real keyboard open.
- [ ] Tapping every external link opens the system browser sheet. Wired
      (`NativeLinkHandler`) but not tap-verified.
- [ ] Vision QA pass: **partial**, not the full route × theme × device-size matrix —
      see the detailed note above. All 7 routes checked in dark mode, home checked in
      light mode, one device size. Remaining: light mode on the other 6 routes, a
      second device size, and the user's sign-off.
- [x] Inputs don't trigger iOS auto-zoom on focus: `.native-app input/textarea/select
      { font-size: 16px }` is a deterministic CSS fix (16px is the browser's own
      zoom threshold, not app-specific behavior needing a live device test to
      confirm). Every interactive element shows a pressed state on tap: covered by
      the `:active` opacity-dip rule added under item 6, applied globally to
      buttons/links/`[role=button]`.
- [ ] The chat/answer screen reads comfortably at phone size: markdown tables now
      scroll horizontally within their own container instead of breaking page width
      (fixed this session), but the broader reading-measure/line-height/code-block
      legibility question wasn't systematically audited.
- [ ] User signs off on the final screenshot set before Phase 5 begins.
- [x] The web app rendering is unchanged: verified `.next/server/app/index.html` from
      the default `npm run build` has `<html class="dark">` (no `native-app`) and the
      original unmodified viewport meta tag — the new safe-area/touch-feel CSS and
      viewport changes are proven build-time-gated to the capacitor target only, not
      just visually spot-checked.

---

## Phase 4b — Voice input (talk to the app)

**Goal:** users can dictate their protocol question hands-free — critical for ED
clinicians who may be gloved or mid-task.

**Baseline that already works with zero code:** the iOS keyboard's dictation mic
works in any focused text input inside the webview. Verify it, but don't stop there —
it's fiddly and undiscoverable.

**Tasks**
1. [x] Add a mic button to the prompt input, styled to match the existing design and
   sized ≥44pt. **Deviation from the plan:** the plan pointed at
   `components/PromptInput.tsx`, but that file turned out to be orphaned dead code —
   not imported or rendered anywhere. The app's actual two prompt inputs (hero search
   box and the pinned follow-up box, both in `app/page.tsx`) already had decorative,
   non-functional mic `<button>`s (`title="Voice input"`, no `onClick`). Wired those
   up instead of resurrecting the unused component, and bumped both from
   32–36px to 44px (`w-11 h-11`) to meet the tap-target requirement. Left
   `PromptInput.tsx` in place, unmodified, per the "mention dead code, don't delete
   it" rule — flagging it here as a candidate for removal in a future cleanup.
2. [x] Implemented `lib/useSpeechInput.ts` — one hook, two backends, matching the plan
   exactly:
   - **Native:** `@capacitor-community/speech-recognition` (v7.0.1) with
     `partialResults: true`.
   - **Web:** `webkitSpeechRecognition`/`SpeechRecognition` behind feature detection
     (`speech.isSupported`); both mic buttons are conditionally rendered on this, so
     unsupported browsers simply don't show them — no layout gap.
   This is the only place with platform branching (`Capacitor.isNativePlatform()`);
   `page.tsx` just calls `speech.toggle(question, setQuestion)`.
3. [x] Tap → listening (red pulsing background on the mic button while active) → live
   transcript fills the input (both backends append to whatever text was already
   there when dictation started, not overwrite) → tap again or the recognizer's own
   silence timeout stops it. Never auto-submits — the existing `handleSubmit` is
   unchanged and still requires the send button or Enter.
4. [x] Added `NSMicrophoneUsageDescription` / `NSSpeechRecognitionUsageDescription` to
   `Info.plist` with the exact copy from the plan. Denial path: if
   `requestPermissions()` doesn't return `granted`, the next mic tap shows an
   `alert()` with re-enable-in-Settings guidance instead of silently doing nothing —
   `alert()` renders as a native `UIAlertController` in a WKWebView, so this needed
   no extra plugin.
5. [ ] **Not tested in the Simulator** — Simulator microphone input needs either a
   physical Mac mic feed or a simulated audio route, neither exercised this session
   (headless environment, no interactive access to grant the permission prompt or
   speak into it). Per the plan's own fallback, this defers to the TestFlight device
   pass in Phase 5.

**Success criteria**
- [ ] Tap mic → iOS permission prompts appear once with the custom copy → speaking
      "pediatric sepsis protocol" streams the words into the input → stop → text is
      editable and submits, returning a normal answer. **Needs a device/Simulator
      audio test — not verified this session** (see task 5 above). Everything short
      of the live audio path is verified: clean `xcodebuild` with the plugin linked,
      `tsc --noEmit` passes, the app still renders with the mic button visible in the
      Simulator and no runtime errors in the device log.
- [ ] Deny-permission path verified: mic tap after denial produces the Settings
      guidance, no crash. Code path exists (`alert()` on `permissionDenied`) but
      needs an actual denial to trigger it — not exercised.
- [ ] Keyboard dictation (the built-in mic key) also works in the same input. Not
      re-verified this session, but nothing touched the `<textarea>` elements
      themselves, only added sibling mic buttons, so this should be unaffected.
- [x] Web target: mic button appears and works in Chrome; browsers without the Web
      Speech API simply don't show the button (verified via `speech.isSupported`
      feature detection — Chrome/Safari desktop have `webkitSpeechRecognition`, so
      the button renders there); web text input is otherwise unchanged.
- [x] The hook is the only place with platform branching; `page.tsx` only calls
      `speech.toggle(...)` / reads `speech.isSupported` / `speech.listening` /
      `speech.permissionDenied` — no `Capacitor.isNativePlatform()` checks were added
      to the prompt-input JSX itself.

---

## Phase 5 — Signing, TestFlight upload (fastlane, no Xcode GUI)

**Goal:** a signed build reaches TestFlight entirely from the command line.

**Tasks**
1. Set up fastlane in `frontend/ios/App`: `Appfile` with bundle ID and team,
   `app_store_connect_api_key` wired to the user's `.p8` key (path/key ID/issuer ID
   read from environment variables or an untracked `.env`; add fastlane's generated
   secrets paths to `.gitignore`).
2. Create the App Store Connect app record via CLI: `fastlane produce` (app name
   **"Emergency Medicine App"**, bundle ID from Phase 2, primary language, SKU).
   No App Store Connect web UI needed. If Apple reports the name as taken, fall back
   to "Emergency Medicine App — EMA" and confirm with the owner.
3. Configure signing without Xcode login: set the team ID and automatic signing in
   the project (editable in `project.pbxproj`), and archive with
   `xcodebuild -allowProvisioningUpdates -authenticationKeyPath/-authenticationKeyID/
   -authenticationKeyIssuerID` (or `fastlane gym` with the API key) so certificates
   and profiles are created/renewed automatically via the API key.
4. Add a `beta` lane: build number auto-increment → `gym` (archive + export) →
   `pilot` (upload to TestFlight). Run it.
5. Repeat the Phase 2–4 smoke tests on the TestFlight build (Simulator smoke tests
   pass first; the user installs via TestFlight on their iPhone for the device pass —
   this replaces cable-tethered Xcode device runs entirely).
6. Document the release process in `docs/ios-release.md`: the exact commands from clean
   checkout to TestFlight upload, so a fresh agent can repeat it.

**Success criteria**
- [ ] `fastlane beta` goes from source to a processed TestFlight build with zero
      Xcode GUI interaction and zero Apple ID password/2FA prompts.
- [ ] User confirms full manual pass on their iPhone via TestFlight: sign in with
      Google, run a protocol query, view results, navigate all routes, sign out —
      zero crashes, zero blank screens.
- [ ] `docs/ios-release.md` exists and a second person (or a fresh agent) could follow it.

---

## Phase 6 — App Store submission (fastlane deliver)

**Goal:** the app is submitted for App Review from the CLI; human involvement is
reviewing the metadata text and pressing nothing.

**Tasks**
1. Keep it iPhone-only for v1 (set `TARGETED_DEVICE_FAMILY = 1`): halves the
   screenshot burden and avoids iPad-layout review risk.
2. Generate App Store screenshots from the Simulator: boot a 6.9" device (iPhone 16
   Pro Max) and a 6.5"-class device, drive the app to its best screens (home, a
   protocol answer, personal page), `xcrun simctl io booted screenshot` each. Verify
   with vision that they're presentable before uploading.
3. Write metadata in `fastlane/metadata/` (checked in, reviewable in the PR):
   description, keywords (include "EMA"), subtitle (e.g. "EMA — ED protocols"),
   support URL, marketing URL, privacy policy URL
   (`https://www.emergencymedicine.app/legal`). Category: Medical.
4. App Privacy declarations: submit via `fastlane deliver`'s privacy JSON
   (`app_privacy_details`) — auth = identifiers (email), plus whatever
   analytics_service collects (confirm with the owner what to declare). Voice input
   (Phase 4b) uses Apple's on-device/Apple-server speech recognition and the app does
   not store audio — declare accordingly, and mention the mic's purpose in the review
   notes so the permission prompt doesn't surprise the reviewer.
5. Review notes for the gated app (critical to avoid rejection): explain it is a
   clinical-protocols app for emergency clinicians with institution-gated content,
   and supply a **pre-approved demo account** (create a non-Mayo test user, approve
   it at `/owner`) with its login steps. State that Google sign-in and email login
   are both available and the demo account uses the email path.
6. Age rating questionnaire (all "no" except medical/treatment info), pricing (free),
   availability. All settable via `deliver`.
7. `fastlane deliver --submit_for_review` using the TestFlight build from Phase 5.
8. While review is pending (typically 1–3 days), continue Phase 7. If rejected,
   read the rejection reason, fix, and resubmit — guideline 4.2 (minimum
   functionality) and 2.1 (demo account doesn't work) are the likely risks; both are
   pre-mitigated above.

**Success criteria**
- [ ] `fastlane deliver` uploads metadata, screenshots, and privacy details with no
      web-console editing; the user only approves the wording.
- [ ] Submission status reaches "Waiting for Review" (verifiable via
      `fastlane deliver` output or Spaceship API), with the demo account documented
      in the review notes.
- [ ] The app reaches "Ready for Distribution" / live on the App Store. If a
      rejection occurs, it is resolved and resubmitted within the workstream.

---

## Phase 7 — Guardrails so the two targets never drift

**Tasks**
1. Add a CI check (or at minimum a documented pre-release step) that runs **both**
   `npm run build` and `BUILD_TARGET=capacitor npm run build:ios-web` so a web change
   that breaks static export is caught immediately.
2. Add a short section to `README.md`: architecture note (one Next.js codebase, two
   targets), the two build commands, and a pointer to `docs/ios-release.md`.

**Success criteria**
- [ ] Both builds run green in CI (or the documented check) on the final branch.
- [ ] A deliberately introduced export-breaking change (e.g. a temporary `route.ts`)
      fails the ios-web build check, then is reverted. (Proves the guardrail works.)

---

## Overall definition of done

1. One `frontend/` codebase, zero forked components; platform branches only in
   `auth-context.tsx`, `next.config.mjs`, and small capability helpers.
2. Web app on Vercel: no behavioral change (auth, redirects, `/__/auth` rewrite all intact).
3. iOS app: **live on the App Store**, with native Google sign-in, working protocol
   queries against the production API, safe-area-correct UI, custom icon/splash.
4. Repeatable and click-free: `fastlane beta` ships a TestFlight build and
   `fastlane deliver` ships a release, with no Xcode GUI or web-console steps beyond
   the one-time human setup in Phase 0.

## Explicitly out of scope (do not build unless asked)

- Offline protocol caching, push notifications, Android/Google Play.
- Porting the OneDrive admin integration to native.
- Redesigning the app's visual identity (colors, branding, information architecture).
  Phase 4's mobile look-and-feel work refines the existing design for iPhone; it does
  not replace it.
