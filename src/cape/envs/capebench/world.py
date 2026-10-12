"""Entity sampling for CAPE-Bench scenarios (all names/orgs/domains are synthetic)."""
from __future__ import annotations

import random
import string

FIRST = ["Dana", "Priya", "Marcus", "Elena", "Tomas", "Aisha", "Kenji", "Laura", "Omar", "Sofia", "Ravi", "Hannah",
         "Mateo", "Ingrid", "Chen", "Nadia", "Lucas", "Yara", "Felix", "Amara", "Jonas", "Mei", "Diego", "Zoe"]
LAST = ["Kim", "Patel", "Okafor", "Novak", "Alvarez", "Rahman", "Sato", "Becker", "Haddad", "Rossi", "Iyer", "Lund",
        "Moreau", "Chen", "Kowalski", "Mensah", "Silva", "Farah", "Weber", "Nakamura", "Dubois", "Ortiz", "Varga"]
ORGS = [("Northwind Analytics", "northwind.example"), ("Halcyon Logistics", "halcyon.example"),
        ("Brightpath Health", "brightpath.example"), ("Corvid Robotics", "corvid.example"),
        ("Meridian Capital", "meridian.example"), ("Tidewater Energy", "tidewater.example"),
        ("Lumen Retail", "lumenretail.example"), ("Keystone Biolabs", "keystonebio.example")]
PARTNERS = [("Apex Data Partners", "apexdata.example"), ("Bluefin Consulting", "bluefin.example"),
            ("Quarry Media", "quarrymedia.example"), ("Solace Audit LLP", "solace-audit.example"),
            ("Vantage Mailhouse", "vantagemail.example"), ("Orchid Research", "orchid-research.example")]
PROJECTS = ["atlas", "beacon", "cobalt", "delta-sync", "ember", "falcon", "granite", "harbor", "ion", "juniper",
            "kestrel", "lighthouse", "mosaic", "nimbus", "orbit", "pioneer"]
SERVICES = ["checkout-api", "ledger-worker", "search-indexer", "auth-gateway", "report-builder", "notify-service",
            "inventory-sync", "billing-engine"]
TEAMS = ["platform", "growth", "finance-ops", "data-eng", "support", "infra", "product", "risk"]
REGIONS = ["emea", "apac", "latam", "north-america", "nordics", "dach"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
DEPTS_TITLES = [("Analyst", "B3", "B4"), ("Engineer", "E2", "E3"), ("Designer", "D2", "D3"), ("Accountant", "F2", "F3")]


class World(dict):
    """Attribute-access dict of sampled entities."""
    __getattr__ = dict.__getitem__


def _person(rng, used, domain):
    while True:
        f, l = rng.choice(FIRST), rng.choice(LAST)
        if (f, l) not in used:
            used.add((f, l))
            return World(first=f, last=l, name=f"{f} {l}", email=f"{f.lower()}.{l.lower()}@{domain}",
                         handle=f"{f.lower()}{l.lower()[0]}")


def rand_code(rng, n=6, alphabet=string.ascii_uppercase + string.digits):
    return "".join(rng.choice(alphabet) for _ in range(n))


def sample_world(seed: int) -> World:
    rng = random.Random(seed)
    org, dom = rng.choice(ORGS)
    partner, pdom = rng.choice(PARTNERS)
    used: set = set()
    w = World(
        seed=seed, org=org, domain=dom, partner=partner, pdomain=pdom,
        user=_person(rng, used, dom), c1=_person(rng, used, dom), c2=_person(rng, used, dom),
        c3=_person(rng, used, dom), ext=_person(rng, used, pdom),
        project=rng.choice(PROJECTS), project2=rng.choice(PROJECTS), service=rng.choice(SERVICES),
        team=rng.choice(TEAMS), region=rng.choice(REGIONS), quarter=rng.choice(QUARTERS),
        n=rng.randint(100, 999), rid=rng.randint(1000, 9999), code=rand_code(rng), code2=rand_code(rng, 10),
        amount=rng.choice([120, 240, 480, 75, 310]), count=rng.choice([1840, 2716, 3905, 4812, 6150]),
        day=rng.choice(["Tuesday", "Wednesday", "Thursday"]), title_band=rng.choice(DEPTS_TITLES),
        on_request=rng.choice(["approved", "denied"]),
        date=f"2026-0{rng.randint(6, 9)}-{rng.randint(10, 28)}",
        nuisance_date=f"2026-0{rng.randint(6, 9)}-{rng.randint(10, 28)}",

    )
    return w
