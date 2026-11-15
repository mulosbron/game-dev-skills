---
name: game-feel
description: Apply when a game "works but feels dead", or when a mechanic has just become playable. The juice, feel and feedback layer.
---

# Game Feel

If a mechanic works, half the job is done. The other half is how it feels. Don't say "done" until the layers below exist; add them, then say done.

## Every player action gets a response on three channels
- **Visual:** flash, scale/squash tween, particles, trail.
- **Audio:** at least 3 variations per event, random pitch ±10%.
- **Temporal:** hitstop (2-4 frames), short decaying screen shake (50-200 ms). Use it rarely; if everything shakes, nothing shakes.

## Per-genre minimums
- **Platformer (3 Affedicilik Mekaniği Şart):** coyote time (~100 ms), jump buffering (~100 ms), corner/ceiling correction (2-5 px nudge), variable jump height, landing squash. Bkz: `platformer-forgiveness/SKILL.md`.
- **Hits / damage:** hitstop, white flash, knockback, screen shake, impact particles & spark, slash trail, damage numbers. See `hit-feedback/SKILL.md`.
- **Top-down / shooter:** muzzle flash, shell casing, recoil pushing the camera, bullet trail.
- **UI:** every click gets a sound + 100 ms scale tween; menu transitions are 150-250 ms, never instant.
- **Camera:** lerp-follow the player, look-ahead in the movement direction, never jitter.

## Performance boundary
60 FPS = 16.67 ms. The feel layer does not eat this budget: particles from a pool, sounds preloaded, shake is a single camera offset.

## Definition of done
If someone watching the game silently doesn't go "ooh" in the first 30 seconds, it isn't done. Make the 30-second loop fun first; content, menus and save system come after.
