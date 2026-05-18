"""Smoke-test the Gemini Search pilot path against the deployed API."""

import argparse
import json
from typing import Dict, Iterable, Tuple

import requests


DEFAULT_API_URL = "https://em-protocol-api-930035889332.us-central1.run.app"
DEFAULT_EMAILS = [
    "jones.derick@mayo.edu",
    "morey.jacob@mayo.edu",
]

TEST_CASES = [
    {
        "name": "general_clinical",
        "query": "How do I manage hyperkalemia with ECG changes?",
        "expected_route": "general_clinical",
        "expected_sources": ["web"],
    },
    {
        "name": "local_protocol",
        "query": "What is our sepsis protocol?",
        "expected_route": "local_protocol",
        "expected_sources": ["local"],
    },
    {
        "name": "personal",
        "query": "Use my personal materials to summarize my uploaded bronchiolitis note.",
        "expected_route": "personal",
        "expected_sources": ["personal"],
    },
]


def corporate_login(api_url: str, email: str) -> Tuple[str, Dict]:
    response = requests.post(
        f"{api_url}/auth/corporate-login",
        json={"email": email},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["idToken"], payload["user"]


def iter_sse_events(response: requests.Response) -> Iterable[Dict]:
    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8")
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if not payload:
            continue
        yield json.loads(payload)


def query(api_url: str, token: str, prompt: str) -> Dict:
    response = requests.post(
        f"{api_url}/query",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": prompt,
            "include_images": False,
            "sources": ["local", "wikem", "pmc", "litfl", "rebelem", "aliem", "personal"],
            "bundle_ids": ["all"],
            "ed_ids": [],
        },
        stream=True,
        timeout=90,
    )
    response.raise_for_status()

    final_event = None
    chunk_count = 0
    for event in iter_sse_events(response):
        if event.get("type") == "chunk":
            chunk_count += 1
        if event.get("type") in {"done", "error"}:
            final_event = event
    if final_event is None:
        raise RuntimeError("Query stream ended without a done or error event")
    final_event["chunk_count"] = chunk_count
    return final_event


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--emails", nargs="*", default=DEFAULT_EMAILS)
    args = parser.parse_args()

    failures = 0

    for email in args.emails:
        token, user = corporate_login(args.api_url, email)
        print(f"USER {email} access_status={user.get('accessStatus')} uid={user.get('uid')}")

        for case in TEST_CASES:
            result = query(args.api_url, token, case["query"])
            route = result.get("route")
            sources = result.get("sources")
            status = "PASS"
            if result.get("type") == "error":
                status = "ERROR"
                failures += 1
            elif route != case["expected_route"] or sources != case["expected_sources"]:
                status = "FAIL"
                failures += 1

            summary = {
                "route": route,
                "sources": sources,
                "model": result.get("model"),
                "grounded": result.get("grounded"),
                "citation_count": len(result.get("citations", [])),
                "chunk_count": result.get("chunk_count", 0),
                "query_time_ms": result.get("query_time_ms"),
                "message": result.get("message"),
            }
            print(f"  {status} {case['name']}: {json.dumps(summary)}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())