#!/usr/bin/env python3
"""
Auto-validator for batch research reports.
Fails on phantom citations or empty evidence.
"""
import json
import sys

def validate_report(report_path: str) -> int:
    """Validate report structure. Returns 0 on success, 1 on failure."""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            r = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Report file not found: {report_path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {report_path}: {e}")
        return 1
    
    src_ids = {s["id"] for s in r.get("sources", [])}
    problems = []
    
    if not r.get("sources"):
        problems.append("FAIL: sources is empty (no evidence ingested)")
    
    for i, f in enumerate(r.get("key_findings", []), 1):
        cits = f.get("citations", [])
        miss = [c for c in cits if c not in src_ids]
        if miss:
            problems.append(f"FAIL: finding #{i} cites unknown ids: {miss}")
        ev = f.get("evidence", [])
        if not ev:
            problems.append(f"FAIL: finding #{i} has no sentence-level evidence")
    
    if problems:
        print("\n".join(problems))
        return 1
    
    print("OK: report passed structural verification.")
    return 0

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/report.json"
    sys.exit(validate_report(path))

