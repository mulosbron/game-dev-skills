---
name: fantasy-first-design
description: Grounds a game idea in player fantasy (who the player wants to be and feel) before locking into mechanics, audits borrowed friction solutions (quest loops, economy, upgrades, UI, settings) vs. copied identity (art, IP, characters, world), and detects clone risk. Use when brainstorming a game concept, pitch, Steam capsule one-liner, asking "why didn't my game sell?", or building something inspired by another game—even if the word "fantasy" is not used.
---

# Fantasy-First Design

Most developers start a game idea with a genre or mechanic and lock themselves into one implementation from day one. Starting with fantasy keeps every door open: "cute bunny platformer" is only a platformer, whereas "a game that makes you feel like the cutest bunny alive" could be a visual novel, a dress-up sim, or an adventure game. Fantasy is also your sales pitch: say "vampire bank robber" and everyone instantly knows what they are buying.

This skill structures your concept into a design brief and audits clone risk deterministically with `scripts/fantasy_brief.py`. Your job is to clarify the fantasy with the user and fill the brief; validation and verdict logic live in the script.

## When to Use Which Tool

Run commands from this skill's directory (`skills/fantasy-first-design/`):

| Request | Tool / Action |
|---|---|
| New game idea, concept, or pitch | `python scripts/fantasy_brief.py --template` to get a blank brief, fill it with the user, then `python scripts/fantasy_brief.py brief.json --output brief.md` |
| "This game is like X—is it a clone?" | Same script: populate `inspirations` and check the verdict |
| Writing a fantasy statement or Steam one-liner | Follow "Find the fantasy" below, write it into the brief, and verify it triggers no genre-first warning |

Exit code `0` means valid, `1` means design warnings or clone risk, and `2` means input error (missing/invalid fields are listed individually—fix and re-run).

## Workflow

1. **Find the fantasy.** Ask: *"Who does the player want to be, or what do they want to feel?"* If the answer is a genre label ("platformer", "roguelike"), step back: what moment inside that genre actually feels good?
2. **Name the craving.** Fantasy satisfies an itch someone already has when browsing for a game. Ask for the user's own craving: *"What game did you play where you thought 'I wish it let me do X'?"* If you want it, others do too.
3. **Note fantasy scale.** Every fantasy has a demand ceiling: cheating your way to winning the World Cup appeals to millions; leading a brutal bloody apocalypse appeals to a narrower niche. Leave empty if audience size does not matter, but check this first when a developer asks why a game did not sell.
4. **Extract inspirations.** List games selling a similar fantasy and what is borrowed from each. Mark `type` as `solution` (a solved, non-core friction piece) or `identity` (art, IP, character, world). For `solution`, `my_context` is required: how are you rebuilding it inside your own setting?
5. **Run the audit and read the verdict.** `scripts/fantasy_brief.py` outputs the verdict and warnings. Resolve clone risk first: strip out identity elements and replace them with the reference game's *design philosophy* (e.g., "everything readable at a glance"). Keyword checks are heuristics—override false positives, but state the reason clearly.
6. **Deliver the brief.** Save the Markdown brief and summarize the fantasy statement, borrowed friction solutions, and uncovered solution areas.

## What to Borrow vs. Never Borrow

The boundary is clear: never clone the game, never take the art, never take the IP. Borrow solved friction instead—interactions readable at a glance, quest loops, between-run upgrade loops, single-currency economies, upgrade structures (a button on a machine works just as well as a skill tree), UI conventions, main menus, settings menus, health systems, and generous checkpoints. These are solved plumbing, not your game's differentiator; reinventing them just makes the game harder to understand.

Seeing someone else sell the same fantasy is good news, not bad news: it proves an audience exists. The winner is the developer who rebuilds that fantasy in their *own* context rather than copying someone else's.

## Caveats (What Scripts Cannot Do)

- The script cannot judge whether a fantasy is compelling or estimate real market demand; it only verifies required fields and checks for borrowed identity. Test the fantasy by asking: *"Is it clear in one sentence, and would anyone crave this?"*
- Genre-term and identity-word detection is keyword-based and can produce false positives; treat warnings as prompts to double-check.
- Factual claims about reference games (such as whether a game uses one currency) must be verified by the user or reliable sources.

## Tests

After modifying `scripts/fantasy_brief.py`, run:

```bash
python -m unittest tests/test_fantasy_brief.py
```

`assets/sample_brief.json` provides a sample brief ("Night Shift") demonstrating both valid solutions and a flagged clone risk.
