# iOS Release Process

How to go from a clean checkout to a build on TestFlight, entirely from the
command line (no Xcode GUI, no Apple ID password/2FA prompts) — except the
one one-time manual step below.

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
3. **App Store Connect app record** — the one step that genuinely needs a
   human with **Account Holder** access (not delegable to any Team API key
   role; Apple restricts `POST /v1/apps` to the account owner). One time only:
   - Confirm the bundle ID is registered:
     `cd frontend/ios/App && set -a && source fastlane/.env && set +a && python3 scripts/register_asc_bundle_id.py`
     (idempotent — registers it via the API directly if not already done, no
     Apple ID needed for *this* part).
   - Then, with an Account Holder login: appstoreconnect.apple.com → Apps →
     **+** → **New App** → bundle ID `app.emergencymedicine.ios`, name
     "Emergency Medicine App", primary language English, SKU
     `app-emergencymedicine-ios`. Takes about a minute.
   - Everything after this point never needs Account Holder access again —
     the App Manager key is sufficient for all builds, uploads, and
     (eventually) submissions.

## Ship a build to TestFlight

```bash
cd frontend
npm run ios:sync                    # rebuild the static export, sync into ios/
cd ios/App
set -a && source fastlane/.env && set +a
fastlane beta
```

`fastlane beta` (see `frontend/ios/App/fastlane/Fastfile`):
1. Bumps the build number past whatever's already on TestFlight
   (`latest_testflight_build_number`).
2. Turns on automatic signing for the `9J4BZ42NBS` team.
3. Archives and exports an app-store build (`gym`), with
   `-allowProvisioningUpdates` so certificates/profiles are created or
   renewed automatically via the API key — no manual profile management.
4. Uploads to TestFlight (`pilot`), not distributed externally by default
   (internal testing only until you choose to release it further).

No Xcode GUI, no Apple ID password, no 2FA prompt at any point.

## After upload

Processing on Apple's side typically takes a few minutes. Once it's done,
install via the TestFlight app on a real device and do a full manual pass:
sign in with Google, run a protocol query, navigate every route, sign out —
see `docs/ios-app-workstream.md` Phase 5 success criteria for the full list.

## Troubleshooting

- **"Team ID not found" / signing errors**: confirm `9J4BZ42NBS` still
  matches `security find-identity -v -p codesigning` output, or look it up
  fresh in Apple Developer → Membership if it's ever rotated.
- **`latest_testflight_build_number` errors "app not found"**: the App Store
  Connect app record from the one-time setup step doesn't exist yet — see
  above.
- **Version bump**: `fastlane beta` only bumps the *build* number, not the
  marketing version (`1.0`). Bump `CFBundleShortVersionString` /
  `MARKETING_VERSION` manually in Xcode or `project.pbxproj` for a new
  release version.
