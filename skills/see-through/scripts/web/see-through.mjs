/**
 * See-through math for Canvas, Phaser and WebGL.
 * Same rules as tools/see_through_lib.py and the SpriteCook guide:
 * https://www.spritecook.ai/blog/2d-see-through-fade-dither-cutout-silhouette
 *
 * Y grows downward. Positions are in world units. `pixelScale` is world units
 * per art pixel (1 when the game draws at art resolution). The character
 * position is the feet, not a centered origin.
 */

export const BAYER_4X4 = [
  0, 8, 2, 10,
  12, 4, 14, 6,
  3, 11, 1, 9,
  15, 7, 13, 5,
];

export const REFERENCE_HEIGHT = 36;

export const Look = {
  FADE: "fade",
  DITHER: "dither",
  DITHERED_FADE: "dithered_fade",
  CUTOUT: "cutout",
  SILHOUETTE: "silhouette",
  OUTLINE: "outline",
  NONE: "none",
};

export const LOOK_CYCLE = [
  Look.FADE,
  Look.DITHER,
  Look.DITHERED_FADE,
  Look.CUTOUT,
  Look.SILHOUETTE,
  Look.OUTLINE,
  Look.NONE,
];

const MASK_LOOKS = new Set([Look.SILHOUETTE, Look.OUTLINE]);
const WINDOW_LOOKS = new Set([Look.DITHER, Look.DITHERED_FADE, Look.CUTOUT]);

export function defaultSettings(over = {}) {
  return {
    charWidth: 20,
    charHeight: 36,
    easeTime: 0.2,
    coverGridX: 3,
    coverGridY: 4,
    coverNeeded: 0.25,
    fadeTo: 0.4,
    clearRadius: 18,
    soft: 16,
    keep: 0,
    holeRadius: 22,
    silhouette: [118, 214, 255],
    outline: [250, 250, 240],
    pixelScale: 1,
    yDown: true,
    ...over,
  };
}

export function scaleRadii(height, referenceHeight = REFERENCE_HEIGHT) {
  const k = height / referenceHeight;
  return { clearRadius: 18 * k, soft: 16 * k, holeRadius: 22 * k };
}

export function settingsForHeight(height, base = defaultSettings()) {
  const radii = scaleRadii(height);
  const width = base.charWidth * (height / base.charHeight);
  return { ...base, charWidth: width, charHeight: height, ...radii };
}

export function moveToward(current, goal, maxDelta) {
  if (current < goal) return Math.min(current + maxDelta, goal);
  if (current > goal) return Math.max(current - maxDelta, goal);
  return current;
}

export function stepAmount(amount, behind, dt, easeTime) {
  const goal = behind ? 1 : 0;
  if (easeTime <= 0) return goal;
  return moveToward(amount, goal, dt / easeTime);
}

export function characterCenter(feetX, feetY, height, yDown = true) {
  const half = height * 0.5;
  return [feetX, yDown ? feetY - half : feetY + half];
}

export function depthBehind(feetY, objectBaseY, yDown = true) {
  return yDown ? feetY < objectBaseY : feetY > objectBaseY;
}

export function coverPoint(feetX, feetY, width, height, ix, iy, gridX = 3, gridY = 4, yDown = true) {
  const atX = ((ix + 0.5) / gridX - 0.5) * width;
  let atY = ((iy + 0.5) / gridY - 1) * height;
  if (!yDown) atY = -atY;
  return [feetX + atX, feetY + atY];
}

export function coverPoints(feetX, feetY, width, height, gridX = 3, gridY = 4, yDown = true) {
  const points = [];
  for (let iy = 0; iy < gridY; iy++) {
    for (let ix = 0; ix < gridX; ix++) {
      points.push(coverPoint(feetX, feetY, width, height, ix, iy, gridX, gridY, yDown));
    }
  }
  return points;
}

export function characterBox(feetX, feetY, width, height, yDown = true) {
  if (yDown) return [feetX - width * 0.5, feetY - height, width, height];
  return [feetX - width * 0.5, feetY, width, height];
}

export function rectsOverlap(a, b) {
  const [ax, ay, aw, ah] = a;
  const [bx, by, bw, bh] = b;
  return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
}

export function coverPasses(hidden, gridX = 3, gridY = 4, coverNeeded = 0.25) {
  return hidden > 0 && hidden >= coverNeeded * gridX * gridY;
}

export function isBehind({
  feetX,
  feetY,
  objectBaseY,
  look,
  opaqueAt = null,
  objectBounds = null,
  settings = defaultSettings(),
}) {
  const { charWidth, charHeight, coverGridX, coverGridY, coverNeeded, yDown } = settings;
  if (!depthBehind(feetY, objectBaseY, yDown)) return false;
  if (MASK_LOOKS.has(look) || look === Look.NONE) {
    if (!objectBounds) throw new Error("silhouette and outline need the occluder bounds");
    return rectsOverlap(characterBox(feetX, feetY, charWidth, charHeight, yDown), objectBounds);
  }
  if (!opaqueAt) throw new Error("fade, dither and cutout need an opaque-pixel test");
  const points = coverPoints(feetX, feetY, charWidth, charHeight, coverGridX, coverGridY, yDown);
  let hidden = 0;
  for (const [x, y] of points) if (opaqueAt(x, y)) hidden += 1;
  return coverPasses(hidden, coverGridX, coverGridY, coverNeeded);
}

export function fadeOpacity(amount, fadeTo) {
  return 1 + (fadeTo - 1) * amount;
}

export function windowParams(look, settings) {
  if (look === Look.CUTOUT) return { radius: settings.holeRadius, soft: 0, keep: 0 };
  if (look === Look.DITHERED_FADE) {
    return {
      radius: settings.clearRadius,
      soft: settings.soft,
      keep: settings.keep > 0 ? settings.keep : 0.375,
    };
  }
  if (look === Look.DITHER) {
    return { radius: settings.clearRadius, soft: settings.soft, keep: settings.keep };
  }
  throw new Error(`${look} does not drop occluder pixels`);
}

export function lookIsNoop(look, settings) {
  if (look === Look.NONE) return true;
  if (look === Look.FADE) return settings.fadeTo >= 1;
  if (look === Look.DITHER || look === Look.DITHERED_FADE) {
    return settings.clearRadius === 0 && settings.soft === 0;
  }
  if (look === Look.CUTOUT) return settings.holeRadius === 0;
  return false;
}

export function solidFraction(distance, amount, radius, soft, keep) {
  const reach = (radius + soft) * amount;
  const solid = soft > 0 ? Math.min(1, Math.max(0, (distance - reach) / soft + 1)) : distance >= reach ? 1 : 0;
  return Math.max(solid, keep);
}

export function bayerValue(cellX, cellY) {
  const x = ((cellX % 4) + 4) % 4;
  const y = ((cellY % 4) + 4) % 4;
  return BAYER_4X4[y * 4 + x];
}

export function shouldDrop(solid, bayer) {
  return solid <= (bayer + 0.5) / 16;
}

export function shouldDropPixel(worldX, worldY, targetX, targetY, amount, radius, soft, keep, pixelScale = 1) {
  const cellX = Math.floor(worldX / pixelScale);
  const cellY = Math.floor(worldY / pixelScale);
  const dx = cellX + 0.5 - targetX / pixelScale;
  const dy = cellY + 0.5 - targetY / pixelScale;
  const distance = Math.hypot(dx, dy);
  return shouldDrop(solidFraction(distance, amount, radius, soft, keep), bayerValue(cellX, cellY));
}

export function occluderAlpha(sourceAlpha, { look, drop, amount, fadeTo }) {
  if (look === Look.FADE) return sourceAlpha * fadeOpacity(amount, fadeTo);
  if (WINDOW_LOOKS.has(look)) return drop ? 0 : sourceAlpha;
  return sourceAlpha;
}

export function flatColorAlpha(sourceAlpha, colorAlpha = 1, threshold = 0.5) {
  return (sourceAlpha >= threshold ? 1 : 0) * colorAlpha;
}

export function outlineAlpha(center, up, down, left, right, colorAlpha = 1, threshold = 0.5) {
  const inside = center >= threshold ? 1 : 0;
  const around = Math.min(up, down, left, right);
  const edge = around >= threshold ? 0 : 1;
  return inside * edge * colorAlpha;
}

export function outlineFromGrid(alpha, colorAlpha = 1, threshold = 0.5) {
  const height = alpha.length;
  const width = height ? alpha[0].length : 0;
  const at = (x, y) => (x < 0 || y < 0 || y >= height || x >= width ? 0 : alpha[y][x]);
  return alpha.map((row, y) =>
    row.map((_, x) => outlineAlpha(at(x, y), at(x, y - 1), at(x, y + 1), at(x - 1, y), at(x + 1, y), colorAlpha, threshold)),
  );
}

/**
 * Zero the alpha of dropped occluder pixels in an ImageData-like buffer.
 * `data` is RGBA bytes, row-major. `originX/Y` is the world position of texel (0, 0).
 * Window looks never change RGB. Returns the number of dropped pixels.
 */
export function applyWindowToRgba(data, width, height, originX, originY, targetX, targetY, look, amount, settings) {
  const noop = lookIsNoop(look, settings);
  const params = !noop && WINDOW_LOOKS.has(look) ? windowParams(look, settings) : null;
  const scale = settings.pixelScale;
  let dropped = 0;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const srcA = data[i + 3];
      let drop = false;
      if (params) {
        drop = shouldDropPixel(
          originX + x * scale,
          originY + y * scale,
          targetX,
          targetY,
          amount,
          params.radius,
          params.soft,
          params.keep,
          scale,
        );
      }
      const next = occluderAlpha(srcA / 255, {
        look,
        drop,
        amount,
        fadeTo: settings.fadeTo,
      });
      data[i + 3] = Math.round(next * 255);
      if (drop && srcA !== 0) dropped += 1;
    }
  }
  return dropped;
}

export function createOccluder({ name, baseY, look = Look.DITHER, bounds, opaqueAt = null, settings = defaultSettings() }) {
  return {
    name,
    baseY,
    look,
    bounds,
    opaqueAt,
    settings,
    amount: 0,
    behind(feetX, feetY) {
      return isBehind({
        feetX,
        feetY,
        objectBaseY: baseY,
        look: this.look,
        opaqueAt: this.opaqueAt,
        objectBounds: this.bounds,
        settings: this.settings,
      });
    },
    step(dt, feetX, feetY) {
      this.amount = stepAmount(this.amount, this.behind(feetX, feetY), dt, this.settings.easeTime);
      return this.amount;
    },
    opacity() {
      return this.look === Look.FADE ? fadeOpacity(this.amount, this.settings.fadeTo) : 1;
    },
    ghostOn() {
      return this.amount > 0 && MASK_LOOKS.has(this.look);
    },
  };
}

export function cycleLook(look) {
  return LOOK_CYCLE[(LOOK_CYCLE.indexOf(look) + 1) % LOOK_CYCLE.length];
}

/** Fragment shader source. Drop-in for a canvas_item / sprite shader. pixelScale 1 matches the tested Godot shader. */
export const SEE_THROUGH_FRAG = `precision highp float;
uniform vec2 uTarget;
uniform float uAmount;
uniform float uRadius;
uniform float uSoft;
uniform float uKeep;
uniform float uPixelScale;
varying vec2 vWorld;
const float BAYER[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
void main() {
  vec2 art = vWorld / uPixelScale;
  vec2 cell = floor(art);
  float d = distance(cell + 0.5, uTarget / uPixelScale);
  float reach = (uRadius + uSoft) * uAmount;
  float solid = uSoft > 0.0 ? clamp((d - reach) / uSoft + 1.0, 0.0, 1.0) : step(reach, d);
  solid = max(solid, uKeep);
  ivec2 c = ivec2(mod(cell, 4.0));
  if (solid <= (BAYER[c.y * 4 + c.x] + 0.5) / 16.0) discard;
}
`;

export const FLAT_COLOR_FRAG = `precision highp float;
uniform sampler2D uTexture;
uniform vec4 uColor;
varying vec2 vUv;
void main() {
  float a = step(0.5, texture2D(uTexture, vUv).a);
  gl_FragColor = vec4(uColor.rgb, a * uColor.a);
}
`;

export const OUTLINE_FRAG = `precision highp float;
uniform sampler2D uTexture;
uniform vec4 uColor;
uniform vec2 uTexel;
varying vec2 vUv;
void main() {
  float inside = step(0.5, texture2D(uTexture, vUv).a);
  float around = min(min(texture2D(uTexture, vUv + vec2(uTexel.x, 0.0)).a,
                         texture2D(uTexture, vUv - vec2(uTexel.x, 0.0)).a),
                     min(texture2D(uTexture, vUv + vec2(0.0, uTexel.y)).a,
                         texture2D(uTexture, vUv - vec2(0.0, uTexel.y)).a));
  gl_FragColor = vec4(uColor.rgb, inside * (1.0 - step(0.5, around)) * uColor.a);
}
`;
