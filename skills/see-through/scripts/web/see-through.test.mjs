import assert from "node:assert/strict";
import {
  Look,
  bayerValue,
  coverPasses,
  createOccluder,
  defaultSettings,
  depthBehind,
  fadeOpacity,
  isBehind,
  lookIsNoop,
  outlineFromGrid,
  scaleRadii,
  settingsForHeight,
  shouldDropPixel,
  stepAmount,
  windowParams,
} from "./see-through.mjs";

const DT = 1 / 60;
const size = { charWidth: 20, charHeight: 36 };

function eased(frames, behind, start = 0) {
  let amount = start;
  for (let i = 0; i < frames; i++) amount = stepAmount(amount, behind, DT, 0.2);
  return amount;
}

const near = (actual, expected, label) => {
  assert.ok(Math.abs(actual - expected) < 1e-9, `${label}: ${actual} != ${expected}`);
};

near(eased(6, true), 0.5, "frame 6");
near(eased(12, true), 1, "frame 12");
near(eased(12, false, 1), 0, "off 12");
assert.equal(stepAmount(0, true, DT, 0), 1);

assert.equal(depthBehind(100, 100), false);
assert.equal(depthBehind(101, 100), false);
assert.equal(depthBehind(99, 100), true);

const always = () => true;
const never = () => false;
assert.equal(isBehind({ feetX: 0, feetY: 100, objectBaseY: 100, look: Look.DITHER, opaqueAt: always }), false);
assert.equal(isBehind({ feetX: 0, feetY: 99, objectBaseY: 100, look: Look.DITHER, opaqueAt: always }), true);
assert.equal(isBehind({ feetX: 0, feetY: 99, objectBaseY: 100, look: Look.FADE, opaqueAt: never }), false);

const pointsNeeded = (n) => {
  let seen = 0;
  return () => {
    seen += 1;
    return seen <= n;
  };
};
assert.equal(coverPasses(2), false);
assert.equal(coverPasses(3), true);
assert.equal(isBehind({ feetX: 0, feetY: 99, objectBaseY: 100, look: Look.CUTOUT, opaqueAt: pointsNeeded(2) }), false);
assert.equal(isBehind({ feetX: 0, feetY: 99, objectBaseY: 100, look: Look.CUTOUT, opaqueAt: pointsNeeded(3) }), true);

assert.equal(fadeOpacity(1, 0.4), 0.4);

const target = [0.5, 0.5];
for (const dist of [0, 10, 17]) {
  assert.equal(shouldDropPixel(dist, 0, target[0], target[1], 1, 18, 16, 0), true, `dither d ${dist}`);
}
for (const dist of [35, 48]) {
  assert.equal(shouldDropPixel(dist, 0, target[0], target[1], 1, 18, 16, 0), false);
}

const kept = [];
for (let y = 0; y < 4; y++) {
  for (let x = 0; x < 4; x++) {
    if (!shouldDropPixel(x, y, 2, 2, 1, 18, 16, 0.375)) kept.push(bayerValue(x, y));
  }
}
assert.deepEqual(kept.sort((a, b) => a - b), [0, 1, 2, 3, 4, 5]);

const kept04 = [];
for (let y = 0; y < 4; y++) {
  for (let x = 0; x < 4; x++) {
    if (!shouldDropPixel(x, y, 2, 2, 1, 18, 16, 0.4)) kept04.push(bayerValue(x, y));
  }
}
assert.deepEqual(kept04.sort((a, b) => a - b), kept.sort((a, b) => a - b));

for (let x = 0; x < 22; x++) assert.equal(shouldDropPixel(x, 0, 0.5, 0.5, 1, 22, 0, 0), true);
assert.equal(shouldDropPixel(22, 0, 0.5, 0.5, 1, 22, 0, 0), false);

assert.equal(lookIsNoop(Look.FADE, defaultSettings({ fadeTo: 1 })), true);
assert.equal(lookIsNoop(Look.DITHER, defaultSettings({ clearRadius: 0, soft: 0, keep: 0.375 })), true);
assert.equal(lookIsNoop(Look.CUTOUT, defaultSettings({ holeRadius: 0 })), true);
assert.deepEqual(windowParams(Look.DITHERED_FADE, defaultSettings()), { radius: 18, soft: 16, keep: 0.375 });
assert.deepEqual(scaleRadii(72), { clearRadius: 36, soft: 32, holeRadius: 44 });
assert.equal(settingsForHeight(72).charWidth, 40);

const alpha = Array.from({ length: 7 }, () => Array(7).fill(0));
for (let y = 1; y <= 5; y++) for (let x = 1; x <= 5; x++) alpha[y][x] = 1;
const edge = outlineFromGrid(alpha);
assert.equal(edge[3][3], 0);
assert.equal(edge[1][1], 1);
assert.equal(edge[0][0], 0);
const flipped = alpha.map((row) => [...row].reverse());
const flippedEdge = outlineFromGrid(flipped);
assert.deepEqual(flippedEdge, edge.map((row) => [...row].reverse()));

const a = createOccluder({
  name: "tree",
  baseY: 100,
  look: Look.DITHER,
  bounds: [0, 40, 40, 60],
  opaqueAt: (x) => x < 40,
});
const b = createOccluder({
  name: "wall",
  baseY: 100,
  look: Look.DITHER,
  bounds: [180, 40, 40, 60],
  opaqueAt: (x) => x > 200,
});
for (let i = 0; i < 12; i++) {
  a.step(DT, 10, 99);
  b.step(DT, 10, 99);
}
near(a.amount, 1, "tree opens");
assert.equal(b.amount, 0);

assert.equal(bayerValue(-1, -1), 5);

console.log("see-through web tests: ok");
