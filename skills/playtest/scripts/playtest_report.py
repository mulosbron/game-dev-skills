#!/usr/bin/env python3
"""Playtest observation reporter: aggregates logs per build and ranks action items.

Each observation during a session is recorded as one CSV row:
    session,tester,build,second,event,location,note,assisted

  session   session identifier (e.g., "0.3-01")
  tester    tester identifier (e.g., "T07"); reuse the same ID if a tester replays
  build     build label being tested (e.g., "0.3.0")
  second    elapsed seconds from session start (integer)
  event     stuck | died | confused | positive | quit
  location  level / room / area name (e.g., "Warehouse", "2nd Bridge")
  note      free-text observation note
  assisted  "yes" if the facilitator told the player what to do at that moment

Counting, ratios, and ranking are deterministic so two reviewers always get the
identical report from the same log.

Usage:
  python playtest_report.py observations.csv               # Markdown report (stdout)
  python playtest_report.py observations.csv --json report.json
  python playtest_report.py observations.csv --build 0.3.0 # filter to one build
  python playtest_report.py --template                     # print CSV header row
"""

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

COLUMNS = ["session", "tester", "build", "second", "event", "location"]
EVENTS = {
    "stuck": "Stuck",
    "died": "Died",
    "confused": "Confused / misunderstood",
    "positive": "Positive reaction",
    "quit": "Quit",
}
ISSUES = ("stuck", "died", "confused")
MIN_TESTERS = 5


def read_observations(path):
    """Read and validate an observation CSV file. Raises ValueError with line numbers."""
    text = Path(path).read_text(encoding="utf-8-sig")
    first = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in COLUMNS if c not in header]
    if missing:
        raise ValueError(
            f"Missing column(s): {', '.join(missing)}. Expected header: {','.join(COLUMNS + ['note', 'assisted'])}"
        )
    records, errors = [], []
    for line_no, row in enumerate(reader, start=2):
        vals = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if not any(vals.get(c) for c in COLUMNS):
            continue
        rec = {c: vals.get(c, "") for c in COLUMNS + ["note", "assisted"]}
        rec["event"] = rec["event"].lower()
        rec["assisted"] = rec["assisted"].lower()
        empty = [c for c in COLUMNS if not rec[c]]
        if empty:
            errors.append(f"line {line_no}: empty required field(s) {', '.join(empty)}")
        elif rec["event"] not in EVENTS:
            errors.append(f"line {line_no}: unknown event '{rec['event']}'. Valid: {', '.join(EVENTS)}")
        else:
            try:
                rec["second"] = int(rec["second"])
            except ValueError:
                errors.append(f"line {line_no}: second must be an integer (got '{rec['second']}')")
                continue
            rec["line"] = line_no
            records.append(rec)
    if errors:
        raise ValueError("Invalid observation file:\n  - " + "\n  - ".join(errors))
    return records


def _mmss(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _natural_sort_key(build):
    """Split build tag so '0.9.0' sorts before '0.10.0'."""
    parts = re.split(r"(\d+)", build)
    return tuple((0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts if p != "")


def summarize(records):
    """Aggregate records per build in natural build order."""
    by_build = {}
    for r in records:
        by_build.setdefault(r["build"], []).append(r)

    result = []
    for build in sorted(by_build, key=_natural_sort_key):
        rows = by_build[build]
        testers = sorted({r["tester"] for r in rows})
        sessions = sorted({r["session"] for r in rows})
        durations = {
            sess: max(r["second"] for r in rows if r["session"] == sess)
            for sess in sessions
        }

        warnings = []
        if len(testers) < MIN_TESTERS:
            warnings.append(
                f"This build was tested with {len(testers)} tester(s); each build requires at least "
                f"{MIN_TESTERS} testers. Do not conclude the build improved with fewer testers."
            )
        if not any(r["event"] in ISSUES for r in rows):
            warnings.append(
                "No issue observations recorded. Either the build had zero friction or confusion/blocks "
                "were not logged; review the raw session notes."
            )

        issues_map, positive_map = {}, {}
        for r in rows:
            if r["event"] in ISSUES:
                bucket = issues_map.setdefault(
                    (r["location"], r["event"]),
                    {"count": 0, "testers": set(), "first": r["second"], "notes": []},
                )
            elif r["event"] == "positive":
                bucket = positive_map.setdefault(
                    r["location"],
                    {"count": 0, "testers": set(), "first": r["second"], "notes": []},
                )
            else:
                continue
            bucket["count"] += 1
            bucket["testers"].add(r["tester"])
            bucket["first"] = min(bucket["first"], r["second"])
            if r["note"]:
                bucket["notes"].append(r["note"])

        def make_row(location, event, b):
            return {
                "location": location,
                "event": event,
                "event_name": EVENTS[event],
                "count": b["count"],
                "tester_count": len(b["testers"]),
                "testers": sorted(b["testers"]),
                "tester_ratio": round(len(b["testers"]) / len(testers), 3),
                "first_second": b["first"],
                "notes": b["notes"],
            }

        issue_rows = sorted(
            (make_row(loc, ev, b) for (loc, ev), b in issues_map.items()),
            key=lambda x: (-x["tester_count"], -x["count"], x["first_second"], x["location"]),
        )
        positive_rows = sorted(
            (make_row(loc, "positive", b) for loc, b in positive_map.items()),
            key=lambda x: (-x["tester_count"], -x["count"], x["location"]),
        )

        assisted = [
            {
                "session": r["session"],
                "tester": r["tester"],
                "second": r["second"],
                "location": r["location"],
                "note": r["note"],
            }
            for r in rows
            if r["assisted"] == "yes"
        ]
        assisted_sessions = sorted({a["session"] for a in assisted})
        if assisted_sessions:
            warnings.append(
                f"Facilitator guided the player in {len(assisted_sessions)} session(s) "
                f"({', '.join(assisted_sessions)}). 99% of players will play without you present; "
                "observations after assistance do not represent unguided play."
            )

        median = statistics.median(durations.values()) if durations else 0
        result.append({
            "build": build,
            "observation_count": len(rows),
            "session_count": len(sessions),
            "tester_count": len(testers),
            "testers": testers,
            "session_durations": durations,
            "median_duration_sec": int(median) if median == int(median) else median,
            "assistance_violations": assisted,
            "assisted_sessions": assisted_sessions,
            "issues": issue_rows,
            "positive": positive_rows,
            "quits": sorted(
                (
                    {
                        "session": r["session"],
                        "tester": r["tester"],
                        "second": r["second"],
                        "note": r["note"],
                    }
                    for r in rows
                    if r["event"] == "quit"
                ),
                key=lambda x: x["second"],
            ),
            "warnings": warnings,
        })

    # Attach previous-build tester counts so regressions and fixes are visible at a glance.
    for i, b in enumerate(result):
        if i == 0:
            continue
        prev = result[i - 1]
        index = {(s["location"], s["event"]): s for s in prev["issues"]}
        for s in b["issues"]:
            old = index.get((s["location"], s["event"]))
            s["previous"] = (
                {
                    "build": prev["build"],
                    "tester_count": old["tester_count"],
                    "tester_total": prev["tester_count"],
                    "count": old["count"],
                }
                if old
                else None
            )
    return result


def _prev_text(s):
    if not s.get("previous"):
        return "—"
    p = s["previous"]
    return f"{p['build']}: {p['tester_count']}/{p['tester_total']}"


def format_report(builds):
    out = ["# Playtest Report", ""]
    if not builds:
        return "\n".join(out + ["No observations found. Start a log using assets/observation_template.csv.", ""])
    total_obs = sum(b["observation_count"] for b in builds)
    out += [f"{len(builds)} build(s), {total_obs} observation(s).", ""]
    for b in builds:
        out += [
            f"## Build {b['build']}",
            "",
            f"- Testers: {b['tester_count']} ({', '.join(b['testers'])})",
            f"- Sessions: {b['session_count']}, observations: {b['observation_count']}, median session duration: {_mmss(b['median_duration_sec'])}",
            f"- Assistance violations: {len(b['assistance_violations'])} observation(s), {len(b['assisted_sessions'])} session(s)",
            "",
        ]
        comparative = bool(b["issues"]) and any(s.get("previous") for s in b["issues"])
        out += [
            "### Issues",
            "",
            "Ordered by most unique testers affected. If players act differently than intended, fix the game design.",
            "",
        ]
        if comparative:
            out += [
                "| Location | Event | Count | Unique Testers | Tester Ratio | Previous Build | First Seen | Notes |",
                "|---|---|---|---|---|---|---|---|",
            ]
        else:
            out += [
                "| Location | Event | Count | Unique Testers | Tester Ratio | First Seen | Notes |",
                "|---|---|---|---|---|---|---|",
            ]
        for s in b["issues"]:
            ratio = f"{s['tester_count']}/{b['tester_count']} ({round(100 * s['tester_ratio'])}%)"
            notes = "; ".join(dict.fromkeys(s["notes"])) or "—"
            base = f"| {s['location']} | {s['event_name']} | {s['count']} | {', '.join(s['testers'])} | {ratio} |"
            if comparative:
                out.append(f"{base} {_prev_text(s)} | {_mmss(s['first_second'])} | {notes} |")
            else:
                out.append(f"{base} {_mmss(s['first_second'])} | {notes} |")
        if not b["issues"]:
            out.append("| (none) | | | | | | |")
        out += [
            "",
            "### Positive Reactions",
            "",
            "| Location | Count | Testers | First Seen | Notes |",
            "|---|---|---|---|---|",
        ]
        for s in b["positive"]:
            notes = "; ".join(dict.fromkeys(s["notes"])) or "—"
            out.append(
                f"| {s['location']} | {s['count']} | {', '.join(s['testers'])} | {_mmss(s['first_second'])} | {notes} |"
            )
        if not b["positive"]:
            out.append("| (none) | | | | |")
        if b["quits"]:
            out += ["", "### Quits", ""]
            out += [
                f"- {x['session']} ({x['tester']}): {_mmss(x['second'])}" + (f" — {x['note']}" if x["note"] else "")
                for x in b["quits"]
            ]
        if b["assistance_violations"]:
            out += ["", "### Assisted Moments", ""]
            out += [
                f"- {y['session']} ({y['tester']}), {_mmss(y['second'])}, {y['location']}" + (f" — {y['note']}" if y["note"] else "")
                for y in b["assistance_violations"]
            ]
        out += ["", "### Warnings", ""]
        out += [f"- {w}" for w in b["warnings"]] or ["- None."]
        out.append("")

    latest = builds[-1]
    out += [f"## Next Steps (build {latest['build']})", ""]
    if not latest["issues"]:
        out.append("No issues to rank. Put the next build in front of at least five testers again.")
    for i, s in enumerate(latest["issues"][:3], 1):
        prev = (
            f"; previous build {s['previous']['tester_count']}/{s['previous']['tester_total']}"
            if s.get("previous")
            else ""
        )
        out.append(
            f"{i}. `{s['location']}`: '{s['event_name'].lower()}' in {s['tester_count']} tester(s) "
            f"({s['count']} time(s){prev}). Redesign this area."
        )
    if latest["issues"]:
        out += [
            "",
            "After each fix: ship a new build, test with at least five testers, log observations, and "
            "re-run this report to verify whether affected tester counts drop.",
        ]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Playtest observation reporter.")
    ap.add_argument("csv", nargs="?", help="Observation log file (CSV)")
    ap.add_argument("--template", action="store_true", help="Print CSV header row and exit")
    ap.add_argument("--build", help="Filter report to a single build label")
    ap.add_argument("--json", metavar="FILE", help="Also write summary to JSON file")
    args = ap.parse_args(argv)

    if args.template:
        print(",".join(COLUMNS + ["note", "assisted"]))
        return 0
    if not args.csv:
        ap.error("csv file is required (or pass --template)")

    try:
        records = read_observations(args.csv)
    except OSError as e:
        print(f"ERROR: could not read file: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if args.build:
        records = [r for r in records if r["build"] == args.build]
    summary = summarize(records)
    sys.stdout.write(format_report(summary))
    if args.json:
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
