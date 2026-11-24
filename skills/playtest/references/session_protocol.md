# Playtest Session Protocol

Players rarely verbalize everything; their facial expressions and body language show whether they are engaged or frustrated. Playtest value comes from running the session properly and logging the right signals.

The four core rules come from the source methodology; the session workflow steps support the CSV format used by `scripts/playtest_report.py`.

## The Four Non-Negotiable Rules

1. **Watch the first playthrough live.** Observe a tester's very first run in real time; do not rely on post-hoc summaries. The game does not need polished art—test whatever playable build you have.
2. **Never tell the player what to do.** Resisting the urge to help when a tester gets stuck is hard, but essential: 99% of players will play without you there. Once you guide a tester, subsequent observations in that session no longer represent unguided play.
3. **Every gameplay problem is a design problem, not player error.** When players behave differently from what you expected, change the game design. "The player didn't get it" is not an excuse—it is an engineering ticket.
4. **At least five testers per build, then repeat.** Test with five or more players, adjust the game based on findings, cut a new build, and test again continuously throughout development.

## Session Workflow

**Before.** Choose a build tag (e.g., `0.3.0`), copy `assets/observation_template.csv`, and assign each tester a persistent ID (like `T07`) reused across future builds.

**During.** Sit beside the player or watch their screen live. Add one row per notable moment:

| Column | What to record |
|---|---|
| `session` | Build + session sequence, e.g., `0.3-07` |
| `tester` | Tester ID (`T07`) |
| `build` | Build tag (`0.3.0`) |
| `second` | Approximate elapsed seconds from session start |
| `event` | `stuck`, `died`, `confused`, `positive`, `quit` |
| `location` | Level, room, or landmark name |
| `note` | What you observed or what the player said |
| `assisted` | `yes` if you guided the player at that moment |

Watch closely for two easily missed signals: **positive reactions** (laughing, leaning in, smiling, admiring a vista—always log the location) and **quiet missed cues** (walking past an interactable, failing to notice a door). When a player gets stuck, write what they *tried*, not just "confused."

**If you had to intervene.** Sometimes intervention is unavoidable (hard crash, soft-lock, player about to quit). Mark `assisted` as `yes` on that row so the report flags the session.

**After.** Run the report:

```bash
python scripts/playtest_report.py observations.csv --json report.json
```

The report tracks unique testers per build (warning if under five), ranks issues by tester count, and lists the top areas to redesign.

## For the Next Build

Fix the top-ranked issue first. Where 4 of 5 testers get stuck is a systemic design flaw; where 1 tester dies is a tuning detail. Ship a new build, append new rows to the same log with the new `build` tag, and re-run the report to confirm affected tester counts decrease. If counts stay flat or rise, your fix treated the symptom rather than the root cause.

## Common Mistakes That Ruin Playtests

- Substituting self-testing for real testers (what feels obvious to you is invisible to a newcomer).
- Explaining or defending mechanics ("actually, you're supposed to..."), which invalidates subsequent observations.
- Stopping after a single tester or single build (one tester is an anecdote; two or more of five is a pattern).
- Counting only deaths (missing doors, wandering in circles, and silent boredom are just as diagnostic).
- Hotfixing mid-session (mixes observations across different builds).
