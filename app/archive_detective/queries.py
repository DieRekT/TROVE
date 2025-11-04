from __future__ import annotations

import csv

from .config import QUERIES_DIR
from .models import TroveQuery


def _rows() -> list[TroveQuery]:
    return [
        TroveQuery(
            label="Ashby village basics",
            query='"Ashby" AND "Clarence River"',
            trove_zone="newspaper",
        ),
        TroveQuery(
            label="Clarence Street mentions",
            query='"Clarence Street" AND (Ashby OR "Clarence River" OR Maclean)',
        ),
        TroveQuery(
            label="Village allotments / sales",
            query='(Ashby AND ("village allotment" OR "town allotment" OR "village of Ashby") AND sale)',
        ),
        TroveQuery(label="Moongi Cottage name", query='"Moongi Cottage" OR ("Moongi" AND Ashby)'),
        TroveQuery(
            label="Parish map references", query='"Parish of Ashby" AND "County of Clarence"'
        ),
        TroveQuery(
            label="Crown land / reserves",
            query='(Ashby AND ("Crown land" OR "Crown Lands") AND (lease OR reserve OR "Conditional Purchase"))',
            date_from="1860-01-01",
            date_to="1930-12-31",
        ),
        TroveQuery(
            label="Aboriginal Reserve AR 55640",
            query='("Aboriginal Reserve" OR "A.R. 55640" OR "Reserve 55640") AND (Ashby OR Maclean OR "Clarence River")',
            date_from="1900-01-01",
            date_to="1960-12-31",
        ),
        TroveQuery(
            label="Council rates / valuations",
            query="(Ashby AND (rates OR valuation) AND council)",
            date_from="1900-01-01",
        ),
        TroveQuery(
            label="Shipping & river traffic",
            query='("Clarence River" AND Ashby AND (wharf OR jetty OR ferry OR "river steamer"))',
            date_from="1860-01-01",
            date_to="1950-12-31",
        ),
        TroveQuery(
            label="Real property notices",
            query='(Ashby AND ("for sale" OR auction) AND (house OR cottage OR farm))',
            date_from="1880-01-01",
        ),
        TroveQuery(
            label="Gazette cross-check",
            query='(Ashby AND ("Crown Lands" OR reserve OR "resumed"))',
            trove_zone="gazette",
        ),
        TroveQuery(
            label="People + street filter",
            query='(Ashby AND "Clarence Street" AND (Mr OR Mrs OR Miss))',
            date_from="1880-01-01",
        ),
    ]


def generate_trove_queries_csv() -> str:
    QUERIES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = QUERIES_DIR / "trove_queries.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["label", "query", "trove_zone", "date_from", "date_to", "notes"])
        for r in _rows():
            w.writerow([r.label, r.query, r.trove_zone, r.date_from, r.date_to, r.notes])
    return str(out_path)
