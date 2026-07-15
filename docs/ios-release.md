# iOS Release Process

How to go from a clean checkout to a build on TestFlight, entirely from the
command line (no Xcode GUI, no Apple ID password/2FA prompts) — except the
two one-time manual steps below.

## One-time setup (per machine)

1. **App Store Connect API key** (see `docs/ios-app-workstream.md` Phase 0):
   a Team Key with **App Manager** role, `.p8` file saved locally. Fill in
   `frontend/ios/App/fastlane/.env` (gitignored):
   ```
   ASC_KEY_ID=...
   ASC_ISSUER_ID=...
   ASC_KEY_PATH=/absolute/path/to/AuthKey_XXXXX.p8
   ```
2. **fastlane**: `brew install fastlane`
3. **App Store Connect app record** — needs a human with **Account Holder**
   access (not delegable to any Team API key role; Apple restricts
   `POST /v1/apps` to the account owner specifically). One time only:
   - Confirm the bundle ID is registered:
     `cd frontend/ios/App && set -a && source fastlane/.env && set +a && python3 scripts/register_asc_bundle_id.py`
     (idempotent — registers it via the API directly if not already done, no
     Apple ID needed for *this* part).
   - Then, with an Account Holder login: appstoreconnect.apple.com → Apps →
     **+** → **New App** → bundle ID `app.emergencymedicine.ios`, name
     "Emergency Medicine App", primary language English, SKU
     `app-emergencymedicine-ios`. Takes about a minute.
4. **Xcode account + Keychain** — needs a human with an interactive GUI
   session (can't be scripted around):
   - Sign into Xcode once: Xcode → Settings → Accounts → add the Apple ID
     for this team. `xcodebuild`, even driven entirely through fastlane with
     an API key, separately requires the team to be "known" to Xcode's own
     Accounts before it will trust locally-installed provisioning profiles —
     confirmed by testing (the API key alone produces
     `error: No Account for Team '<team>'`, regardless of
     `-allowProvisioningUpdates` or explicit `-authenticationKey*` flags).
   - The first time `fastlane beta` creates a new Apple Distribution
     certificate, macOS may pop up a Keychain "allow this tool to use your
     private key?" dialog when signing embedded frameworks. Run `fastlane
     beta` once from a normal interactive Terminal (not a sandboxed/headless
     shell) and click **Always Allow** — this is permanent, one time only.
   - Every subsequent `fastlane beta` run needs neither of these again.

**Important — find your real Team ID first.** `security find-identity -v
-p codesigning` may show a personal/free "Apple Development" team that is
*different* from the paid Developer Program team tied to your App Store
Connect API key and app record. Verify by checking the `seedId` returned
when registering the bundle ID (`register_asc_bundle_id.py`'s underlying
`POST /v1/bundleIds` response) — that `seedId` is the real Team ID to put in
`fastlane/Appfile` and `fastlane/Fastfile`. Using the wrong (personal) team
ID produces the same "No Account for Team" error and is easy to
misdiagnose as an Xcode sign-in problem when it's actually just the wrong ID.

## Ship a build to TestFlight

```bash
cd frontend
npm run ios:sync                    # rebuild the static export, sync into ios/
cd ios/App
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8   # fastlane errors without a UTF-8 locale
set -a && source fastlane/.env && set +a
fastlane beta
```

`fastlane beta` (see `frontend/ios/App/fastlane/Fastfile`):
1. Bumps the build number past whatever's already on TestFlight
   (`latest_testflight_build_number`).
2. Switches to **manual** signing (not automatic) with an explicit
   certificate + profile name. `xcodebuild -allowProvisioningUpdates`
   couldn't resolve a team/profile via the API key alone in testing here —
   it kept reporting "No Account for Team" even with the API key's
   authentication flags passed straight to xcodebuild — so signing is
   handled explicitly with the actions below rather than left for
   xcodebuild to sort out automatically at archive time.
3. `get_certificates` + `get_provisioning_profile`: create/fetch a
   distribution cert and an App Store provisioning profile via the API key
   (`Spaceship::ConnectAPI` — this part *does* work non-interactively, no
   Apple ID needed). Then explicitly copies the downloaded profile into
   `~/Library/MobileDevice/Provisioning Profiles/<UUID>.mobileprovision` —
   neither `sigh`'s own "Installing..." step nor the `install_provisioning_
   profile` fastlane action reliably put it there in testing, so this is
   done by hand in the lane.
4. `gym`: archives and exports an app-store `.ipa` using that specific
   cert/profile (manual signing style).
5. `pilot`: uploads to TestFlight, not distributed externally by default
   (internal testing only until you choose to release it further).

No Xcode GUI, no Apple ID password, no 2FA prompt at any point — once the
one-time setup above is done.

## After upload

Processing on Apple's side typically takes a few minutes. Once it's done,
install via the TestFlight app on a real device and do a full manual pass:
sign in with Google, run a protocol query, navigate every route, sign out —
see `docs/ios-app-workstream.md` Phase 5 success criteria for the full list.

## Troubleshooting

- **"No Account for Team '<id>'" even after signing into Xcode**: you're
  probably using the wrong team ID — see "find your real Team ID first"
  above. Check `security find-identity -v -p codesigning` for an "Apple
  Distribution" (not "Apple Development") identity; its team ID in
  parentheses should match the `seedId` from the bundle ID registration.
- **`codesign` hangs / `errSecInternalComponent` on embedded frameworks
  (e.g. `FBSDKLoginKit.framework`, pulled in transitively by
  `@capacitor-firebase/authentication` regardless of which providers you
  configure — there's no clean way to exclude it)**: this is the Keychain
  private-key dialog described in the one-time setup above. Run `fastlane
  beta` from an interactive Terminal once and click Always Allow.
- **fastlane crashes with `"Cr" on UTF-16` / `Encoding::InvalidByteSequenceError`**:
  locale isn't UTF-8. `export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8` before
  running fastlane.
- **`latest_testflight_build_number` errors "app not found"**: the App Store
  Connect app record from the one-time setup step doesn't exist yet — see
  above.
- **Version bump**: `fastlane beta` only bumps the *build* number, not the
  marketing version (`1.0`). Bump `CFBundleShortVersionString` /
  `MARKETING_VERSION` manually in Xcode or `project.pbxproj` for a new
  release version.
