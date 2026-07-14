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
- [ ] `npm run ios:sync` completes without errors.
- [ ] App launches in the iOS Simulator, renders the home page, and all six routes are
      reachable by in-app navigation.
- [ ] Protocol search/chat against the FastAPI backend works in the Simulator (network
      calls to `NEXT_PUBLIC_API_URL` succeed — verify the production API URL is baked
      into the ios-web build via `.env` used at build time, and that the API's CORS
      config allows the `capacitor://localhost` / `ionic://localhost` origins; add them
      to the FastAPI CORS middleware if not).
- [ ] Zero uncaught JS errors in the Safari Web Inspector attached to the Simulator app
      during a pass through every page.

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
2. In `lib/auth-context.tsx` only, branch `signInWithGoogle`:
   - `Capacitor.isNativePlatform()` → native plugin sign-in, then bridge the returned
     ID token into the JS SDK with `signInWithCredential(auth, GoogleAuthProvider.credential(idToken))`
     so the existing `onAuthStateChanged` listeners, Firestore access, and API token
     logic all keep working unmodified.
   - Web → existing popup/redirect code path, untouched.
3. Handle sign-out symmetrically (plugin sign-out + JS SDK sign-out on native).
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
- [ ] In the Simulator: tapping "Sign in with Google" completes the native Google flow
      and returns to the app signed in; the user's profile/personal page loads with
      their data; authenticated API calls to the FastAPI backend succeed.
- [ ] Gating parity with web, verified for all three cases in the Simulator:
      a @mayo.edu Google account gets `accessStatus: "approved"` and sees protocols;
      a non-Mayo Google account lands in `no_access` and can submit an access request
      that appears at `/owner`; corporate passwordless login works end to end and the
      session survives an app force-quit and relaunch (Preferences-backed tokens).
- [ ] Sign out in the app, relaunch the app: still signed out. Sign in, force-quit,
      relaunch: still signed in (persistence works).
- [ ] On the web (`npm run dev` and the Vercel preview): Google sign-in behaves exactly
      as before — the web code path has zero changes in its diff.

---

## Phase 4 — iOS polish (make it feel like an app, not a webpage)

**Tasks**
1. Safe areas: set `viewport-fit=cover` in the root layout's viewport meta, and pad the
   header/footer with `env(safe-area-inset-top/bottom)` — apply via a `.native-app` class
   or CSS that is harmless on web.
2. Status bar: `@capacitor/status-bar`, style matched to the app's theme.
3. Splash screen + app icon: `@capacitor/splash-screen` and generated icon set from the
   existing logo assets in `logos/` (use `@capacitor/assets` to generate all sizes).
4. Keyboard: `@capacitor/keyboard`, verify the chat/prompt input isn't obscured when the
   keyboard opens.
5. External links (training video link, legal pages' outbound links, OneDrive if present)
   must open in the system browser (`@capacitor/browser` or `window.open` interception),
   not navigate the webview away from the app.
6. Disable webview affordances that feel non-native: text selection callouts where
   inappropriate, pinch zoom (`user-scalable=no` for the native build), rubber-band
   overscroll if it looks wrong.
7. Known scope note: the admin/owner OneDrive integration may not work in the webview
   (OAuth popup). If broken, hide that control on native (`isNativePlatform()` check) —
   do not attempt to port it in this workstream.

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
- [ ] On a notched-device Simulator (e.g. iPhone 16 Pro): no content under the notch or
      home indicator; status bar legible on every page.
- [ ] Custom app icon and splash screen appear (not Capacitor defaults).
- [ ] With the keyboard open, the active text input is fully visible.
- [ ] Tapping every external link opens the system browser sheet; the app never gets
      "stuck" on an external site with no way back.
- [ ] Vision QA pass complete: screenshots of every route × {light, dark} × {small,
      large iPhone} reviewed against the look-and-feel checklist, with zero remaining
      findings (no horizontal overflow, no truncation, no sub-44pt targets, no
      default-web-styled controls, correct dark mode colors).
- [ ] Inputs don't trigger iOS auto-zoom on focus; every interactive element shows a
      pressed state on tap.
- [ ] The chat/answer screen reads comfortably at phone size: protocol markdown
      (including tables) renders without breaking layout, and the input stays usable
      with the keyboard open.
- [ ] User signs off on the final screenshot set before Phase 5 begins.
- [ ] The web app rendering is unchanged (visually verify home + one inner page on
      `npm run dev`).

---

## Phase 4b — Voice input (talk to the app)

**Goal:** users can dictate their protocol question hands-free — critical for ED
clinicians who may be gloved or mid-task.

**Baseline that already works with zero code:** the iOS keyboard's dictation mic
works in any focused text input inside the webview. Verify it, but don't stop there —
it's fiddly and undiscoverable.

**Tasks**
1. Add a mic button to the prompt input (`components/PromptInput.tsx`), styled to
   match the existing design and sized ≥44pt.
2. Implement one shared hook (e.g. `lib/useSpeechInput.ts`) with two backends behind
   the same interface — keeping the one-codebase rule:
   - **Native:** `@capacitor-community/speech-recognition` (wraps Apple's on-device
     `SFSpeechRecognizer`), with `partialResults: true` so words stream into the
     input live as the user speaks.
   - **Web:** the Web Speech API (`webkitSpeechRecognition`) behind feature
     detection; hide the mic button in browsers that lack it. Web behavior today is
     otherwise unchanged.
3. Interaction: tap mic → listening state (visible pulse/indicator) → live
   transcript fills the input → tap again (or silence timeout) stops. **Do not
   auto-submit** — this is a medical app; the user reviews and edits the transcript,
   then sends. Mid-dictation edits and appending to existing text must not crash.
4. Permissions: add `NSMicrophoneUsageDescription` and
   `NSSpeechRecognitionUsageDescription` to `Info.plist` with honest, specific copy
   ("Dictate your protocol question instead of typing"). Handle denial gracefully:
   tapping the mic after denial shows how to re-enable in Settings, never a dead
   button or a crash.
5. Test in the Simulator (Simulator mic uses the Mac microphone; if speech
   recognition is unreliable there, defer final verification to the TestFlight
   device pass in Phase 5 and say so explicitly).

**Success criteria**
- [ ] Tap mic → iOS permission prompts appear once with the custom copy → speaking
      "pediatric sepsis protocol" streams the words into the input → stop → text is
      editable and submits, returning a normal answer.
- [ ] Deny-permission path verified: mic tap after denial produces the Settings
      guidance, no crash.
- [ ] Keyboard dictation (the built-in mic key) also works in the same input.
- [ ] Web target: mic button appears and works in Chrome; browsers without the Web
      Speech API simply don't show the button; web text input is otherwise unchanged.
- [ ] The hook is the only place with platform branching; `PromptInput.tsx` has no
      `isNativePlatform()` checks.

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
