# Example Conversion: Prose to Script-Backed Router

A short before-and-after example showing how the same workflow looks as pure prose versus a script-backed router.

## Task

Whenever a repository cuts a release, increment the `patch` number in `version.json`, prepend a dated heading to `CHANGELOG.md`, and create a git tag.

## Before: Model-Only Prose Skill

```markdown
## Workflow
1. Read `version.json` and parse major, minor, and patch numbers.
2. Increment the patch number. If the user asked for a "major release", increment major and reset minor and patch.
3. Rewrite the file preserving indentation and valid JSON.
4. Read `CHANGELOG.md` and prepend a new heading with today's ISO date.
5. Run git add, git commit, and git tag using a "v" prefix.
6. Report the new version to the user.
```

Problems: "if the user asked for" invites drift, preserving formatting and valid JSON is pure mechanical work, and every step burns tokens repeatedly.

## After: Router + Deterministic Script

`scripts/bump_version.py --major` reads `version.json`, increments the right field, preserves formatting, fails fast on invalid JSON, creates the git tag, and prints the new version on one line. `tests/test_version.py` verifies six cases.

```markdown
## When to Use Which Tool

| Situation | Command |
|---|---|
| Patch release | `python scripts/bump_version.py` |
| Minor or major release | `python scripts/bump_version.py --minor` / `--major` |

## Workflow

1. **Determine release type.** Check the changelog and ask the user if unclear; do not guess.
2. **Run the bumper.** `scripts/bump_version.py` updates version, changelog, and git tag deterministically, reporting any invalid input.
3. **Share the result.** Present the new version and changelog header to the user.
```

Now the model only makes the one judgment call (which release tier is intended); everything mechanical executes identically every time.

## Lint Verification

Running `scripts/skill_lint.py` after conversion:

- In the Before version, steps 2–5 are flagged as `SUGGESTION` script candidates.
- In the After version, every step either calls a `.py` script explicitly or represents human/model judgment, leaving zero `SUGGESTION` findings.
