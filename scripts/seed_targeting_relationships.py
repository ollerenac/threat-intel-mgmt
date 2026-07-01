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

# ISO3 codes required by OpenCTI's LocationMiniMapTargets — map polygons match
# feature.properties.ISO3 against x_opencti_aliases (HomeDashboard "Targeted countries")
COUNTRY_ISO3 = {
    "United States of America": "USA",
    "Ukraine": "UKR",
    "Germany": "DEU",
    "France": "FRA",
    "South Korea": "KOR",
    "Japan": "JPN",
    "Netherlands": "NLD",
    "Saudi Arabia": "SAU",
    "Iraq": "IRQ",
    "Iran": "IRN",
    "United Kingdom": "GBR",
    "Turkey": "TUR",
    "Guam": "GUM",
}

# Documented actor → exploited CVE pairs (CISA/NSA advisories, vendor reporting).
# HomeDashboard "Most active vulnerabilities" counts `targets` rels toType Vulnerability.
GROUP_CVES = {
    "APT28": ["CVE-2023-23397"],
    "APT29": ["CVE-2019-19781", "CVE-2019-11510", "CVE-2018-13379"],
    "Lazarus Group": ["CVE-2021-44228", "CVE-2017-0144"],
    "APT41": ["CVE-2019-19781", "CVE-2021-44228", "CVE-2020-10189"],
    "Sandworm Team": ["CVE-2019-10149"],
    "Kimsuky": ["CVE-2017-11882"],
    "OilRig": ["CVE-2017-11882"],
    "MuddyWater": ["CVE-2020-0688", "CVE-2017-11882"],
    "Volt Typhoon": ["CVE-2021-40539"],
    "Scattered Spider": ["CVE-2015-2291"],
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

    # Create referenced countries missing from OpenCTI (ipinfo only creates seen ones)
    for name, iso3 in COUNTRY_ISO3.items():
        if name in country_ids:
            continue
        obj = api.location.create(
            type="Country",
            name=name,
            x_opencti_aliases=[iso3],
        )
        country_ids[name] = obj["id"]
        countries_raw.append({"name": name, "id": obj["id"], "x_opencti_aliases": [iso3]})
        print(f"  [created country] {name} ({iso3})")

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

    # --- Add ISO3 aliases to countries (map widget polygon matching) ---
    print("Patching country ISO3 aliases...")
    for name, iso3 in COUNTRY_ISO3.items():
        if name not in country_ids:
            continue
        country = next(c for c in countries_raw if c["name"] == name)
        aliases = country.get("x_opencti_aliases") or []
        if iso3 in aliases:
            print(f"  [ok] {name} already has {iso3}")
            continue
        api.stix_domain_object.update_field(
            id=country_ids[name],
            input={"key": "x_opencti_aliases", "value": aliases + [iso3]},
        )
        print(f"  [patched] {name} += {iso3}")

    # --- Create actor → targets → CVE relationships (vulnerabilities widget) ---
    print("Creating CVE targeting relationships...")
    cve_created = 0
    for group_name, cves in GROUP_CVES.items():
        if group_name not in group_ids:
            continue
        for cve in cves:
            vulns = api.vulnerability.list(
                filters={"mode": "and", "filters": [{"key": "name", "values": [cve]}], "filterGroups": []}
            )
            if not vulns:
                print(f"  [cve not found] {cve}")
                continue
            rel = api.stix_core_relationship.create(
                fromId=group_ids[group_name],
                toId=vulns[0]["id"],
                relationship_type="targets",
                description=f"{group_name} has exploited {cve} in the wild (documented).",
            )
            if rel:
                cve_created += 1
                print(f"  [rel] {group_name} → targets → {cve}")

    print(f"\nDone. Created {created} sector/country + {cve_created} CVE relationships. Skipped {skipped} groups.")
    print("Refresh OpenCTI dashboard — widgets should now show data.")


if __name__ == "__main__":
    main()
