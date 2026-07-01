#!/usr/bin/env python3
"""Diagnose dashboard widget data: counts of targets/exploits relationships."""

import os
from dotenv import load_dotenv
from pycti import OpenCTIApiClient

load_dotenv()
api = OpenCTIApiClient(
    os.getenv("OPENCTI_URL", "http://localhost:8080"),
    os.getenv("OPENCTI_ADMIN_TOKEN"),
    ssl_verify=False,
)

def count_rels(rel_type, to_types=None):
    filters = {"mode": "and", "filters": [{"key": "relationship_type", "values": [rel_type]}], "filterGroups": []}
    if to_types:
        filters["filters"].append({"key": "toTypes", "values": to_types})
    rels = api.stix_core_relationship.list(filters=filters, first=500)
    return rels

targets_all = count_rels("targets")
print(f"targets rels total: {len(targets_all)}")

by_totype = {}
for r in targets_all:
    t = r["to"]["entity_type"] if r.get("to") else "?"
    by_totype[t] = by_totype.get(t, 0) + 1
print(f"targets by toType: {by_totype}")

# sample country rel dates
country_rels = [r for r in targets_all if r.get("to") and r["to"]["entity_type"] == "Country"]
if country_rels:
    s = country_rels[0]
    print(f"sample country rel: {s['from']['name'] if s.get('from') else '?'} -> {s['to']['name']}")
    print(f"  created: {s.get('created')}, start_time: {s.get('start_time')}, created_at: {s.get('created_at')}")

exploits = count_rels("exploits")
print(f"\nexploits rels total: {len(exploits)}")

related_vuln = api.stix_core_relationship.list(
    filters={"mode": "and", "filters": [{"key": "toTypes", "values": ["Vulnerability"]}], "filterGroups": []},
    first=100,
)
print(f"rels pointing AT Vulnerability (any type): {len(related_vuln)}")
by_rt = {}
for r in related_vuln:
    by_rt[r["relationship_type"]] = by_rt.get(r["relationship_type"], 0) + 1
print(f"  by rel type: {by_rt}")
if related_vuln:
    s = related_vuln[0]
    print(f"  sample: {s['from']['name'] if s.get('from') else '?'} -{s['relationship_type']}-> {s['to']['name']} (created {s.get('created')})")
