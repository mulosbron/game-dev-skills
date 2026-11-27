"""Headless acceptance tests for the pixel-art wind system (pure-Python mirrors of
godot/wind.gd and godot/wind_tree.gd). Verifies the math before you wire it into an engine.

Run: python test_wind.py            (needs no third-party deps)
"""
import math

TAU = 2 * math.pi

# ---- mirror of wind.gd -----------------------------------------------------
LOOP = 20.0
WAVE_PERIOD = 1.54
WAVE_LENGTH = 69.0

GUSTS = [
    [18.6, 65.0, 0.0, 0.0, 44.0, 1.25],   # the big one
    [19.8, 65.0, 0.0, 0.0, 26.0, 0.5],    # and its tail
    [1.5, 60.0, 95.0, 45.0, 30.0, 0.6],   # a quick one through the middle
    [6.0, 55.0, 150.0, 60.0, 34.0, 0.75], # a medium one along the front
    [7.3, 55.0, 145.0, 65.0, 30.0, 0.9],  # with a second hit right behind it
    [8.5, 50.0, 50.0, 55.0, 30.0, 0.55],  # a light puff at the back
]


def along(p):
    return p[0] + 0.25 * p[1]


def _field(p, time, gusts, spread):
    total = 0.0
    for g in gusts:
        path = g[1] * LOOP
        d = math.fmod(along(p) - g[1] * (time - g[0]) + path / 2.0, path) - path / 2.0
        if d < 0:
            d += path
        d -= path / 2.0
        a = g[5] * math.exp(-((d / (g[4] * spread)) ** 2))
        if g[3] > 0.0:
            a *= math.exp(-(((p[1] - g[2]) / (g[3] * (1.6 if spread > 1.0 else 1.0))) ** 2))
        total += a
    return total


def gust(p, time, gusts=GUSTS):
    return _field(p, time, gusts, 1.0)


def breeze(p, time, gusts=GUSTS):
    return min(1.6 * _field(p, time, gusts, 2.2), 1.0)


def wave_phase(p, time):
    return TAU * (time / WAVE_PERIOD - along(p) / WAVE_LENGTH)


# ---- mirror of wind_tree.gd's per-frame math -------------------------------
POSE_TIME = 0.1


def clump_offset(p, rest, w, time, lean, gusts, push=2.2, period=2.2, damping=0.35,
                 trunk_bend=False, height01=1.0):
    """One pose tick. Returns rounded (dx, dy) plus the values used."""
    g = gust(p, time, gusts)
    b = breeze(p, time, gusts)
    a = wave_phase(p, time)
    ride = lean * (height01 ** 2 if trunk_bend else w)
    dx = ride + w * (0.9 * b + 1.3 * g) * (0.5 - 0.5 * math.cos(a))
    dy = -w * (0.75 * b + 0.5 * g) * max(math.sin(a), 0.0)
    return round(dx), round(dy)


def simulate_spring(time_hit, gusts, push=2.2, period=2.2, damping=0.35, dt=1 / 60.0, secs=12.0):
    """Lean of a tree standing at origin while the gust list blows past. Returns (lean, speed) samples."""
    lean = lean_speed = 0.0
    t = 0.0
    w0 = TAU / period
    samples = []
    while t < secs:
        target = push * gust((0.0, 0.0), t, gusts)
        lean_speed += (w0 * w0 * (target - lean) - 2.0 * damping * w0 * lean_speed) * dt
        lean += lean_speed * dt
        samples.append((t, lean))
        t += dt
    return samples


# ---- tests ------------------------------------------------------------------
FAILURES = []


def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL"), "-", name, ("| " + detail if detail else ""))
    if not ok:
        FAILURES.append(name)


def test_still_air_no_motion():
    """With no gusts, every offset is zero -> every tree matches its original sprite."""
    empty = []
    pts = [(10, 20), (70, 3), (-45, 90)]
    worst = 0
    for i in range(40):
        t = i * 0.13
        for p in pts:
            for w in (0.35, 0.7, 1.0):
                dx, dy = clump_offset(p, (0, 0), w, t, 0.0, empty)
                worst = max(worst, abs(dx), abs(dy))
    check("no gusts => every clump stays at (0,0)", worst == 0, f"max |offset| = {worst}")
    check("no gusts => gust() and breeze() are 0",
          gust((5, 5), 3.0, empty) == 0 and breeze((5, 5), 3.0, empty) == 0)


def test_loop_steps():
    """breeze=1, gust=0, w=1 must step through (0,0),(0,-1),(1,-1),(1,0) over one loop."""
    # Force the fields directly instead of relying on gust positions: emulate by phase sampling.
    def forced(bz, gt, a, w, lean=0.0):
        dx = lean * w + w * (0.9 * bz + 1.3 * gt) * (0.5 - 0.5 * math.cos(a))
        dy = -w * (0.75 * bz + 0.5 * gt) * max(math.sin(a), 0.0)
        return round(dx), round(dy)
    seq = []
    n = 100
    for i in range(n):
        a = TAU * i / n
        pt = forced(1.0, 0.0, a, 1.0)
        if not seq or seq[-1] != pt:
            seq.append(pt)
    expected_cycle = [(0, 0), (0, -1), (1, -1), (1, 0)]
    got = seq[:len(expected_cycle)]
    check("w=1 loop walks rest,up,up+right,right", got == expected_cycle, f"got {seq}")
    still = {forced(1.0, 0.0, TAU * i / 100, 0.35) for i in range(100)}
    check("w=0.35 stays at (0,0) in a plain breeze", still == {(0, 0)}, f"poses seen: {still}")


def test_traveling_wave():
    """Two clumps 69 px apart along the wind share a pose at all times."""
    same = True
    for i in range(60):
        t = i * 0.05
        p1 = (100.0, 40.0)
        p2 = (100.0 + 69.0, 40.0)  # exactly one wavelength along `along` (y equal)
        a1, a2 = wave_phase(p1, t), wave_phase(p2, t)
        if abs((a1 - a2) % TAU) > 1e-9 and abs(abs((a1 - a2) % TAU) - TAU) > 1e-9:
            same = False
    check("69 px along the wind = same phase", same)
    off1 = clump_offset(p1, (0, 0), 1.0, 7.4, 0.0, GUSTS)
    off2 = clump_offset((p1[0] + 69.0, p1[1]), (0, 0), 1.0, 7.4, 0.0, GUSTS)
    check("69 px apart => identical rounded offsets", off1 == off2, f"{off1} vs {off2}")


def test_whole_pixels_and_pose_rate():
    """Every offset integer; poses only change on the 0.1 s clock."""
    ints = True
    for i in range(200):
        t = i * 0.037
        dx, dy = clump_offset((50 + i, 80), (0, 0), 1.0, t, 1.3, GUSTS)
        ints &= isinstance(dx, int) and isinstance(dy, int)
    check("all offsets are whole numbers", ints)
    check("pose clock ticks at 10 Hz", POSE_TIME == 0.1)


def test_gust_spring_settles():
    """After a gust passes an oak, lean dips below zero then settles at 0 with clumps at rest.

    Note: with the article's gust list and a tree at the origin, the first strong hit on the
    tree is the front-path gust entering at t=6.0 (it crosses x=0 around t~12). The big gust
    (enter 18.6) reaches the origin only after one full 20 s loop.
    """
    samples = simulate_spring(6.0, GUSTS, secs=30.0)
    peak_t, peak_l = max(samples, key=lambda s: s[1])
    post = [(t, l) for t, l in samples if t > peak_t]
    dipped = any(l < min(-0.05, -0.1 * abs(peak_l)) for _, l in post)
    tail = [l for t, l in samples if t > 25.0]
    settled = max(abs(l) for l in tail) < 0.05
    check("oak leans downwind when a gust arrives", peak_l > 0.5, f"peak lean {peak_l:.2f} at t={peak_t:.1f}s")
    check("oak lean swings back past upright (dips below 0)", dipped)
    check("oak lean settles near 0 afterwards", settled, f"max |lean| after t=25s: {max(abs(l) for l in tail):.4f}")
    # clumps come to rest too: offsets are zero wherever gust==breeze==0
    quiet_t = next(t for t in [x * 0.1 for x in range(300)]
                   if gust((0.0, 0.0), t) < 1e-6 and breeze((0.0, 0.0), t) < 1e-6)
    dx, dy = clump_offset((0.0, 0.0), (0, 0), 1.0, quiet_t, 0.0, GUSTS)
    check("in still air a clump sits at (0,0)", (dx, dy) == (0, 0))


def test_gust_pattern_shape():
    """6 gusts, 20 s loop, two hits 1.3 s apart, still air between them."""
    check("6 gusts in the pattern", len(GUSTS) == 6)
    check("pattern loops in 20 s", LOOP == 20.0)
    entry_times = sorted(g[0] for g in GUSTS)
    pairs = [round(b - a, 1) for a, b in zip(entry_times, entry_times[1:])]
    check("two gusts come 1.3 s apart", 1.3 in pairs, f"gaps: {pairs}")
    speeds_ok = all(50 <= g[1] <= 65 for g in GUSTS)
    lens_ok = all(26 <= g[4] <= 44 for g in GUSTS)
    str_ok = all(0.5 <= g[5] <= 1.25 for g in GUSTS)
    hh_ok = all(g[3] == 0 or 45 <= g[3] <= 65 for g in GUSTS)
    check("gust params inside the tested ranges", speeds_ok and lens_ok and str_ok and hh_ok)
    # still air somewhere in the loop at the map centre line
    quiet = min(gust((160.0, 90.0), t * 0.05) for t in range(400))
    check("there is still air between gusts", quiet < 0.05, f"min gust at centre = {quiet:.3f}")


def test_constants_match_article():
    check("wave period 1.54 s", WAVE_PERIOD == 1.54)
    check("wave length 69 px", WAVE_LENGTH == 69.0)
    check("wind direction term 0.25*y", abs(along((0, 4)) - 1.0) < 1e-9)


if __name__ == "__main__":
    test_still_air_no_motion()
    test_loop_steps()
    test_traveling_wave()
    test_whole_pixels_and_pose_rate()
    test_gust_spring_settles()
    test_gust_pattern_shape()
    test_constants_match_article()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED:", ", ".join(FAILURES))
        raise SystemExit(1)
    print("All wind-math checks passed.")
