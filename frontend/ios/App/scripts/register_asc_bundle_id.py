#!/usr/bin/env python3
"""
Registers the app's bundle ID with Apple via the App Store Connect API
directly (JWT signed with the .p8 key) — no Apple ID login, no fastlane
`produce` (which requires legacy Apple ID auth for this step even with an
API key, see docs/ios-app-workstream.md Phase 5 task 2).

Idempotent: safe to re-run: checks if the bundle ID already exists before
creating it. Does NOT create the App Store Connect app record itself
(POST /v1/apps requires Account Holder access, not delegable via any Team
API key role) — that's the one remaining manual step, documented in
docs/ios-app-workstream.md.

Requires: pip install PyJWT cryptography
Reads credentials from environment variables (see fastlane/.env):
  ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_PATH
"""

import json
import os
import time
import urllib.error
import urllib.request

import jwt

KEY_ID = os.environ["ASC_KEY_ID"]
ISSUER_ID = os.environ["ASC_ISSUER_ID"]
KEY_PATH = os.environ["ASC_KEY_PATH"]
BUNDLE_ID = "app.emergencymedicine.ios"
APP_NAME = "Emergency Medicine App"


def make_token() -> str:
    with open(KEY_PATH) as f:
        private_key = f.read()
    return jwt.encode(
        {
            "iss": ISSUER_ID,
            "iat": int(time.time()),
            "exp": int(time.time()) + 1200,
            "aud": "appstoreconnect-v1",
        },
        private_key,
        algorithm="ES256",
        headers={"kid": KEY_ID, "typ": "JWT"},
    )


def call(token: str, method: str, path: str, body: dict | None = None):
    url = f"https://api.appstoreconnect.apple.com/v1{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    token = make_token()

    status, res = call(token, "GET", f"/bundleIds?filter[identifier]={BUNDLE_ID}")
    if status != 200:
        raise SystemExit(f"GET bundleIds failed: {status} {res}")

    existing = res.get("data", [])
    if existing:
        print(f"Bundle ID already registered: {existing[0]['id']}")
        return

    status, res = call(
        token,
        "POST",
        "/bundleIds",
        {
            "data": {
                "type": "bundleIds",
                "attributes": {
                    "identifier": BUNDLE_ID,
                    "name": APP_NAME,
                    "platform": "IOS",
                },
            }
        },
    )
    if status != 201:
        raise SystemExit(f"POST bundleIds failed: {status} {json.dumps(res, indent=2)}")

    print(f"Registered bundle ID: {res['data']['id']}")


if __name__ == "__main__":
    main()
