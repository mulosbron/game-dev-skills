---
name: skill-to-script
description: Converts prose-heavy agent skills or repetitive step-by-step model workflows into deterministic script-backed skills, trims SKILL.md down to a clean "when to call which script" router, parameterizes scripts, and lints skill folders. Use when a skill runs inconsistently, wastes tokens, needs automation, becomes hard to discover in a growing repo, or when reviewing and refactoring skills.
---

# Skill to Script

Prose instructions to an LLM are advice, not guarantees—they are never followed identically on every run. When teams write skills for everything in pure prose, agents eventually skip steps and maintainers end up saying "well, skills are just suggestions." If you need deterministic work to run the exact same way 100% of the time, split the job cleanly:

- **Move to a script:** tasks that yield identical output for identical input (counting, sorting, validating, formatting, math, file organization).
- **Keep in the model:** tasks requiring judgment (interpretation, taste, user conversation, resolving ambiguity).
- **Keep in `SKILL.md`:** the minimal router telling the model which script to call in each situation.

That reduces the model's job to understanding user intent and calling the right script—something even smaller, cheaper models do reliably.

## When to Use Which Tool

Run commands from this skill's directory (`skills/skill-to-script/`):

| Situation | Action / Script |
|---|---|
| User has a skill with inconsistent or costly runs | `python scripts/skill_lint.py SKILL_DIR`; fix every ERROR and WARNING, then review every SUGGESTION |
| Auditing multiple skills or a whole skillset | `python scripts/audit_skills.py SKILL1 SKILL2 ...` (runs unit tests + `scripts/skill_lint.py` together) |
| Batch lint report across multiple skills | `python scripts/skill_lint.py SKILL1 SKILL2 ... --output report.md --json result.json` |
| Repetitive prose workflow with no script yet | Follow steps 2–4 below, then lint |
| Need a concrete before/after conversion example | Read `references/example_conversion.md` |

Exit code `0` means zero errors, `1` means at least one `ERROR` (skill may fail to load or trigger), and `2` means a folder could not be read.

## Workflow

1. **Classify each step.** Would two people following this step reach the exact same output? If yes, make it a script candidate. If it depends on judgment, taste, or user dialogue, keep it as prose—never force it into code.
2. **Write the script.** Turn deterministic logic into CLI code. Accept parameters via CLI flags, place sample data under `assets/`, fail with non-zero exit codes listing every missing or invalid field, and put unit tests under `tests/`.
3. **Parameterize rather than hardcode.** When new requirements appear over time, turn hardcoded constants into CLI flags instead of duplicating branches. Periodically review scripts and promote assumptions into parameters.
4. **Shrink `SKILL.md` into a router.** Use a concise `Situation -> Command` table and move lengthy rationale into `references/`. Always cite scripts by exact `scripts/<name>.py` filename rather than vague prose like "generate the report."
5. **Lint and audit.** Run `scripts/skill_lint.py` and `scripts/audit_skills.py` to catch unmentioned scripts, untested scripts, vague phrasing, and remaining script-candidate steps.
6. **Prevent discovery sprawl.** As a skill repository grows, keep each skill focused on a single responsibility with crisp trigger terms in `description`—never bloat descriptions.

## What Never Belongs in Scripts

- Qualitative critique or taste calls (numbers come from scripts; editorial decisions come from the model).
- User dialogue, priority trade-offs, and clarifying questions.
- Unstructured free-text extraction—have the model structure input into JSON or CSV first, then pass it to a deterministic script.

## Caveats (What Scripts Cannot Do)

- The linter inspects text and structure, not live model behavior. Treat `SUGGESTION` steps as a review checklist; verify real improvements by running evals before and after conversion.
- Structural limits (`500` body lines, `1024` character description) reflect Agent Skills format constraints.
- Relying on `SKILL.md` reduces—but does not eliminate—the chance a model forgets to invoke a script; for mission-critical checks, invoke scripts directly from the command line or CI.

## Tests

After editing `scripts/skill_lint.py` or `scripts/audit_skills.py`, run:

```bash
python -m unittest tests/test_skill_lint.py
```

Then run `scripts/skill_lint.py` against all target skills to confirm zero `ERROR` findings remain.
