---
name: playtest
description: Runs structured playtest sessions, logs observations into CSV, and generates build-over-build reports with prioritized fix lists; enforces at least five testers per build, live first-playthrough observation, zero handholding, and treating gameplay friction as a design issue. Use when testing a game with players, planning a playtest or beta test, summarizing session notes or observation logs, or asking "how should I playtest this?"
---

# Playtest

The value of a playtest is not in numbers alone—it is in the method. Putting even an unfinished build in front of someone else and watching their first playthrough is the only way to see where players struggle with things you assumed were obvious. Every successful indie developer relies on this loop continuously throughout production.

This skill counts, ranks, and compares observations deterministically via `scripts/playtest_report.py`. Running the session and taking notes is your (or the user's) job; see `references/session_protocol.md` for the full session workflow.

## When to Use Which Tool

Run commands from this skill's directory (`skills/playtest/`):

| Situation | Action / Script |
|---|---|
| User is preparing a playtest or asks "how should I test this?" | Read `references/session_protocol.md`, walk them through the protocol, and copy `assets/observation_template.csv` |
| Observation log is ready (CSV, table, or messy session notes) | `python scripts/playtest_report.py observations.csv --json report.json` |
| Notes are unstructured prose | Convert into CSV columns `session,tester,build,second,event,location,note,assisted`; mark estimated values clearly |
| Report for a single build only | `python scripts/playtest_report.py observations.csv --build 0.3.0` |

The script stops on errors and lists the exact line number and reason (unknown `event`, empty required column, non-integer `second`). Fix the listed rows and re-run.

## Workflow

1. **Enforce the protocol.** Remind the user of the four rules before testing: watch the first playthrough live, do not guide stuck players, treat every issue as a design problem rather than player error, and test with at least five testers per build.
2. **Structure the log.** Convert verbal or written notes into the 8-column CSV format. When timestamps are missing, estimate `second` and append `"estimated"` to `note`. Whenever the facilitator helped a player, set `assisted` to `yes`—never hide it; the report flags those sessions so later observations are interpreted accurately.
3. **Run the report.** `scripts/playtest_report.py` outputs tester counts per build, issues ranked by unique testers affected, and positive reactions. For builds after the first, the table also shows how many testers hit the same issue in the previous build.
4. **Interpret and prioritize.** The report's "Next steps" section lists the top issues in the latest build. Present those first—an issue hit by 1 tester matters, but comes after a blocker hitting 4 of 5 testers. If an issue increased compared to the prior build, the fix missed the root cause; fix where the problem originates, not just where it surfaces.

## Log Positive Reactions Too

Players rarely say everything aloud—they laugh, lean forward, or pause to admire a view. Log those moments as `positive` with the `location`. The report tracks positive reactions so you know what already works and avoid breaking good moments during future fixes.

## Caveats (What Scripts Cannot Do)

- Numbers in the report reflect log quality. Sparse notes do not mean a bug-free game; if a build has zero logged issues, the script warns you to verify whether observations were actually recorded.
- Five testers is a minimum threshold. Do not claim a build "improved" with fewer than five testers; the script flags under-tested builds explicitly.
- If the same tester plays a build twice, keep the same `tester` ID so unique tester counts remain accurate.
- Root cause is not in the CSV—read the notes, inspect what the player tried, and state clearly when inferring *why* an issue occurred.

## Tests

After modifying `scripts/playtest_report.py`, run:

```bash
python -m unittest tests/test_playtest.py
```

`assets/sample_observations.csv` contains a two-build sample log to preview report formatting.
