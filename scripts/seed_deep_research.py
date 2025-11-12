#!/usr/bin/env python3
import os
import json
import sys
import time
import requests


BASE = os.environ.get("TROVEING_BASE", "http://127.0.0.1:8000")


def post(path, payload):
    r = requests.post(BASE + path, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    print("Seeding sample research presets…")
    out = post("/api/research/seed", {"preset": "all"})
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print("Done.")


if __name__ == "__main__":
    main()

