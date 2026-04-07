#!/usr/bin/env python3
"""
PMC Discovery
Fetches all PMCIDs from target EM journals (2015–present) via NCBI Entrez API.
Deduplicates across journals and saves a discovery manifest.

Usage:
    # Set env vars first
    export ENTREZ_EMAIL="your@email.com"
    export ENTREZ_API_KEY="your_key"

    # Run discovery
    python pmc_discovery.py

    # Force re-discovery (overwrite cached results)
    python pmc_discovery.py --force
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path

from Bio import Entrez

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

Entrez.email = os.environ.get("ENTREZ_EMAIL", "")
Entrez.api_key = os.environ.get("ENTREZ_API_KEY", "")

if not Entrez.email:
    print("⚠️  Set ENTREZ_EMAIL env var (required by NCBI)")
    print("   export ENTREZ_EMAIL='your@email.com'")

JOURNALS = [
    # ── Emergency Medicine (existing) ────────────────────────────────────────
    "Annals of Emergency Medicine",
    "Acad Emerg Med",                                           # Academic Emergency Medicine
    "Journal of the American College of Emergency Physicians Open",
    "The American Journal of Emergency Medicine",
    "The Journal of Emergency Medicine",
    "The Western Journal of Emergency Medicine",
    "Advanced Journal of Emergency Medicine",
    "Eur J Emerg Med",                                          # European Journal of Emergency Medicine
    "Prehospital Emergency Care",
    "Air Medical Journal",
    "Pediatric Emergency Care",
    "CJEM",                                                     # Canadian Journal of Emergency Medicine (EMA-20)

    # ── Critical Care / Resuscitation (EMA-21 to EMA-27) ────────────────────
    "Crit Care Med",                                            # Critical Care Medicine (SCCM) — EMA-21
    "J Intensive Care Med",                                     # Journal of Intensive Care Medicine — EMA-22
    "Resuscitation",                                            # Resuscitation — EMA-23
    "Resuscitation Plus",                                       # Resuscitation Plus (open access) — EMA-24
    "Shock",                                                    # Shock — EMA-25
    "Chest",                                                    # CHEST — EMA-26
    "Am J Respir Crit Care Med",                                # AJRCCM (ATS) — EMA-27

    # ── JAMA Family (EMA-6 to EMA-15) ───────────────────────────────────────
    "JAMA",                                                     # JAMA — EMA-6
    "JAMA Netw Open",                                           # JAMA Network Open — EMA-7
    "JAMA Intern Med",                                          # JAMA Internal Medicine — EMA-8
    "JAMA Pediatr",                                             # JAMA Pediatrics — EMA-9
    "JAMA Cardiol",                                             # JAMA Cardiology — EMA-10
    "JAMA Surg",                                                # JAMA Surgery — EMA-11
    "JAMA Neurol",                                              # JAMA Neurology — EMA-12
    "JAMA Oncol",                                               # JAMA Oncology — EMA-13
    "JAMA Ophthalmol",                                          # JAMA Ophthalmology — EMA-14
    "JAMA Otolaryngol Head Neck Surg",                          # JAMA Otolaryngology — EMA-15

    # ── High-Impact General (EMA-5, EMA-16 to EMA-19) ───────────────────────
    "N Engl J Med",                                             # NEJM — EMA-5
    "Lancet",                                                   # The Lancet — EMA-16
    "Lancet Neurol",                                            # The Lancet Neurology — EMA-16
    "Lancet Infect Dis",                                        # The Lancet Infectious Diseases — EMA-16
    "Lancet Respir Med",                                        # The Lancet Respiratory Medicine — EMA-16
    "BMJ",                                                      # BMJ — EMA-17
    "Ann Intern Med",                                           # Annals of Internal Medicine — EMA-18
    "Mayo Clin Proc",                                           # Mayo Clinic Proceedings — EMA-19
]

DATE_FILTER = "2015/01/01:3000/12/31[PDAT]"  # 2015 to present
BATCH_SIZE = 500
MAX_PER_JOURNAL = 9999  # NCBI ESearch hard cap — use EDirect for >9,999

# Paths
SCRIPT_DIR = Path(__file__).parent
DISCOVERY_DIR = SCRIPT_DIR / "discovery"
DISCOVERY_PATH = DISCOVERY_DIR / "pmc_discovery.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pmc-discovery")

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def fetch_ids_for_journal(journal: str) -> list[dict]:
    """
    Fetch all PMCIDs for a journal from 2015 to present.
    Returns list of {"pmcid": "PMC...", "journal": "..."}
    """
    term = f'"{journal}"[JOUR] AND {DATE_FILTER}'

    # Get total count first (with retry)
    for attempt in range(3):
        try:
            handle = Entrez.esearch(db="pmc", term=term, retmax=0)
            record = Entrez.read(handle)
            handle.close()
            break
        except Exception as e:
            if attempt == 2:
                log.error(f"  Failed to get count for {journal}: {e}")
                return []
            time.sleep(2 ** attempt)

    total = int(record["Count"])
    log.info(f"  {journal}: {total:,} articles (2015–present)")

    if total == 0:
        return []

    if total > MAX_PER_JOURNAL:
        log.warning(f"  ⚠️  {journal} has {total:,} articles — capped at {MAX_PER_JOURNAL:,} (NCBI ESearch limit)")

    total_to_fetch = min(total, MAX_PER_JOURNAL)
    ids = []

    for start in range(0, total_to_fetch, BATCH_SIZE):
        # NCBI hard cap: retstart must be < 9999
        if start >= 9999:
            break
        batch_size = min(BATCH_SIZE, 9999 - start)

        for attempt in range(3):
            try:
                handle = Entrez.esearch(
                    db="pmc",
                    term=term,
                    retstart=start,
                    retmax=batch_size,
                    sort="pub_date",
                )
                record = Entrez.read(handle)
                handle.close()
                ids.extend(record["IdList"])
                break
            except Exception as e:
                if attempt == 2:
                    log.warning(f"  ⚠️  Batch at offset {start} failed after 3 attempts: {e}")
                else:
                    wait = 2 ** (attempt + 1)
                    log.info(f"  Retry {attempt+1} for offset {start} (waiting {wait}s)...")
                    time.sleep(wait)

        # Rate limiting: conservative 0.2s with API key to avoid disconnects
        time.sleep(0.2)

    # Normalize PMCIDs
    articles = []
    for raw_id in ids:
        pmcid = str(raw_id)
        if not pmcid.startswith("PMC"):
            pmcid = f"PMC{pmcid}"
        articles.append({"pmcid": pmcid, "journal": journal})

    return articles


def run_discovery(force: bool = False) -> dict:
    """
    Discover all PMCIDs across all journals.
    Deduplicates by PMCID (keeps first journal seen).
    """
    if DISCOVERY_PATH.exists() and not force:
        log.info(f"Discovery cache exists at {DISCOVERY_PATH}")
        log.info("Use --force to re-discover")
        with open(DISCOVERY_PATH) as f:
            data = json.load(f)
        log.info(f"Cached: {data['total_unique']:,} unique articles")
        return data

    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)

    log.info(f"Discovering articles from {len(JOURNALS)} journals (2015–present)...")
    log.info(f"Entrez email: {Entrez.email or '(not set)'}")
    log.info(f"Entrez API key: {'set' if Entrez.api_key else 'NOT SET (rate limited to 3/sec)'}")
    print()

    all_articles = []
    by_journal = {}
    start_time = time.time()

    for i, journal in enumerate(JOURNALS, 1):
        log.info(f"[{i}/{len(JOURNALS)}] Querying: {journal}")
        articles = fetch_ids_for_journal(journal)
        by_journal[journal] = len(articles)
        all_articles.extend(articles)

    # Deduplicate by PMCID (keep first occurrence)
    seen = set()
    unique_articles = []
    duplicates = 0
    for article in all_articles:
        if article["pmcid"] not in seen:
            seen.add(article["pmcid"])
            unique_articles.append(article)
        else:
            duplicates += 1

    elapsed = time.time() - start_time

    result = {
        "discovered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "date_filter": "2015-present",
        "total_raw": len(all_articles),
        "duplicates_removed": duplicates,
        "total_unique": len(unique_articles),
        "by_journal": by_journal,
        "discovery_time_seconds": round(elapsed, 1),
        "articles": unique_articles,
    }

    with open(DISCOVERY_PATH, "w") as f:
        json.dump(result, f, indent=2)

    log.info("")
    log.info("=" * 60)
    log.info("PMC DISCOVERY COMPLETE")
    log.info("=" * 60)
    log.info(f"  Journals queried:    {len(JOURNALS)}")
    log.info(f"  Total raw IDs:       {len(all_articles):,}")
    log.info(f"  Duplicates removed:  {duplicates:,}")
    log.info(f"  Unique articles:     {len(unique_articles):,}")
    log.info(f"  Time:                {elapsed:.1f}s")
    log.info(f"  Saved to:            {DISCOVERY_PATH}")
    log.info("")
    log.info("  By journal:")
    for journal, count in sorted(by_journal.items(), key=lambda x: -x[1]):
        log.info(f"    {count:>6,}  {journal}")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="PMC Article Discovery")
    parser.add_argument("--force", action="store_true", help="Re-discover even if cache exists")
    args = parser.parse_args()
    run_discovery(force=args.force)


if __name__ == "__main__":
    main()
