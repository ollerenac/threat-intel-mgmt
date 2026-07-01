#!/usr/bin/env python3
"""
Seed OpenCTI with Sector Identity objects and 'targets' relationships
linking ATT&CK intrusion sets to sectors and countries.

Fixes: Most Targeted Victims + Targeted Countries dashboard widgets.

Usage:
    python3 scripts/seed_targeting_relationships.py

Reads OPENCTI_URL and OPENCTI_TOKEN from .env (or environment).
"""

import os
import sys
from dotenv import load_dotenv
from pycti import OpenCTIApiClient

load_dotenv()

OPENCTI_URL = os.getenv("OPENCTI_URL", "http://localhost:8080")
OPENCTI_TOKEN = os.getenv("OPENCTI_ADMIN_TOKEN")

if not OPENCTI_TOKEN:
    sys.exit("ERROR: OPENCTI_ADMIN_TOKEN not set in .env")

# ATT&CK group → (sectors, country_names)
# Source: MITRE ATT&CK group pages (targeted sectors / regions metadata)
GROUP_TARGETING = {
    "APT28": (["Government Administration", "Defense", "Military"], ["United States of America", "Ukraine", "Germany", "France"]),
    "APT29": (["Government Administration", "Think Tanks", "Research"], ["United States of America", "Germany", "Netherlands"]),
    "Lazarus Group": (["Financial Services", "Healthcare", "Defense"], ["United States of America", "South Korea", "Japan"]),
    "APT41": (["Healthcare", "Telecommunications", "Financial Services", "Government Administration"], ["United States of America", "India", "Japan", "South Korea"]),
    "Sandworm Team": (["Energy", "Government Administration", "Transportation"], ["Ukraine", "United States of America", "Germany"]),
    "Kimsuky": (["Government Administration", "Research", "Think Tanks"], ["South Korea", "United States of America", "Japan"]),
    "OilRig": (["Energy", "Government Administration", "Financial Services"], ["Saudi Arabia", "Iraq", "Iran"]),
    "FIN7": (["Financial Services", "Hospitality", "Retail"], ["United States of America", "Germany", "United Kingdom"]),
    "Turla": (["Government Administration", "Defense", "Research"], ["Germany", "France", "Ukraine", "United States of America"]),
    "Winnti Group": (["Healthcare", "Telecommunications", "Manufacturing"], ["Germany", "Japan", "South Korea"]),
    "Scattered Spider": (["Financial Services", "Telecommunications"], ["United States of America", "United Kingdom"]),
    "MuddyWater": (["Government Administration", "Telecommunications", "Energy"], ["Turkey", "Iraq", "Saudi Arabia"]),
    "Volt Typhoon": (["Government Administration", "Defense", "Energy", "Transportation"], ["United States of America", "Guam"]),
}

SECTOR_NAMES = [
    "Government Administration",
    "Defense",
    "Military",
    "Financial Services",
    "Healthcare",
    "Energy",
    "Telecommunications",
    "Transportation",
    "Research",
    "Think Tanks",
    "Manufacturing",
    "Retail",
    "Hospitality",
]


def main():
    print(f"Connecting to {OPENCTI_URL}...")
    api = OpenCTIApiClient(OPENCTI_URL, OPENCTI_TOKEN, ssl_verify=False)

    # --- Create Sector Identity objects ---
    print("Creating sector identities...")
    sector_ids = {}
    for name in SECTOR_NAMES:
        existing = api.identity.list(
            filters={"mode": "and", "filters": [{"key": "name", "values": [name]}, {"key": "entity_type", "values": ["Sector"]}], "filterGroups": []}
        )
        if existing:
            sector_ids[name] = existing[0]["id"]
            print(f"  [exists] {name}")
        else:
            obj = api.identity.create(
                type="Sector",
                name=name,
                description=f"Organizations in the {name} sector.",
            )
            sector_ids[name] = obj["id"]
            print(f"  [created] {name}")

    # --- Fetch existing Countries ---
    print("Fetching countries from OpenCTI...")
    countries_raw = api.location.list(
        filters={"mode": "and", "filters": [{"key": "entity_type", "values": ["Country"]}], "filterGroups": []},
        getAll=True,
    )
    country_ids = {c["name"]: c["id"] for c in countries_raw}
    print(f"  Found {len(country_ids)} countries")

    # --- Fetch Intrusion Sets ---
    print("Fetching intrusion sets from OpenCTI...")
    intrusion_sets = api.intrusion_set.list(getAll=True)
    group_ids = {g["name"]: g["id"] for g in intrusion_sets}
    print(f"  Found {len(group_ids)} intrusion sets")

    # --- Create 'targets' relationships ---
    print("Creating targets relationships...")
    created = 0
    skipped = 0

    for group_name, (sectors, countries) in GROUP_TARGETING.items():
        if group_name not in group_ids:
            print(f"  [not found] {group_name} — skipping")
            skipped += 1
            continue

        group_id = group_ids[group_name]

        for sector_name in sectors:
            if sector_name not in sector_ids:
                continue
            rel = api.stix_core_relationship.create(
                fromId=group_id,
                toId=sector_ids[sector_name],
                relationship_type="targets",
                description=f"{group_name} targets {sector_name} organizations.",
            )
            if rel:
                created += 1
                print(f"  [rel] {group_name} → targets → {sector_name}")

        for country_name in countries:
            if country_name not in country_ids:
                print(f"  [country not found] {country_name}")
                continue
            rel = api.stix_core_relationship.create(
                fromId=group_id,
                toId=country_ids[country_name],
                relationship_type="targets",
                description=f"{group_name} targets organizations in {country_name}.",
            )
            if rel:
                created += 1
                print(f"  [rel] {group_name} → targets → {country_name}")

    print(f"\nDone. Created {created} relationships. Skipped {skipped} groups (not in OpenCTI).")
    print("Refresh OpenCTI dashboard — widgets should now show data.")


if __name__ == "__main__":
    main()
