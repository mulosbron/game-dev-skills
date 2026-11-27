"""Split a pixel art tree into a trunk, a dark "inside" and one PNG per leaf clump, all on the tree's own canvas,
so the layers line up when you stack them at the same position.
Run: python split_tree.py oak.png oak_layers
     python split_tree.py bush.png bush_layers 3 10 0     (min_dist, min_size, trunk_part)
Deps: numpy scipy scikit-image Pillow
Source technique: https://www.spritecook.ai/blog/pixel-art-trees-wind-animation
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.feature import peak_local_max
from skimage.segmentation import watershed


def add_outline(solid, clump, bark, reach=2):
    """The dark outline around the canopy is brown, so the wood test leaves it on the trunk layer, and it would stay
    behind when its clump moves. Give each outline pixel (within `reach` px of the transparent edge) to the clump next
    to it, unless it sits as close to the trunk's solid inside or to pale bark."""
    edge_d = ndimage.distance_transform_edt(solid)                  # distance to the transparent outside
    free = solid & (clump == 0)
    clump_d, (iy, ix) = ndimage.distance_transform_edt(clump == 0, return_indices=True)
    body = free & ((edge_d > reach) | bark)
    body_d = ndimage.distance_transform_edt(~body) if body.any() else np.full(solid.shape, np.inf)
    join = free & (edge_d <= reach) & (clump_d <= reach + 1) & (clump_d < body_d) & (body_d > 1)
    out = clump.copy()
    out[join] = clump[iy[join], ix[join]]
    return out


def split_tree(path, out_dir, min_dist=5, min_size=25, trunk_part=0.4):
    img = Image.open(path).convert("RGBA")
    spr = np.asarray(img)
    solid = spr[..., 3] > 0
    hsv = np.asarray(img.convert("RGB").convert("HSV")).astype(float)
    hue, sat = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255
    lum = spr[..., :3] @ np.array([0.3, 0.59, 0.11])

    # leaves: everything that isn't brown wood or pale bark, above the roots
    wood = (hue >= 5) & (hue < 40) & (sat > 0.22) & (lum < 125)
    bark = (sat < 0.16) & (lum > 95)
    rows = np.nonzero(solid.any(1))[0]
    above_roots = np.arange(spr.shape[0])[:, None] < rows[0] + (rows[-1] - rows[0]) * 0.78
    leaves = solid & ~wood & ~bark & above_roots

    # one clump per bright leaf mass: the bright spots are the seeds, the darker lines between them the borders
    smooth = ndimage.gaussian_filter(np.where(solid, lum, 0), 1.6)
    peaks = peak_local_max(smooth, min_distance=int(min_dist), labels=leaves.astype(int), exclude_border=False)
    seeds = np.zeros(solid.shape, int)
    seeds[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
    clump = watershed(-smooth, seeds, mask=leaves)
    low = rows[-1] - (rows[-1] - rows[0]) * trunk_part     # clumps centred below this line don't move
    for k in range(1, clump.max() + 1):
        ys = np.nonzero(clump == k)[0]
        if len(ys) < min_size or ys.mean() > low:
            clump[clump == k] = 0                 # crumbs and moss on the trunk stay on the trunk layer
    clump = add_outline(solid, clump, bark)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    def save(mask, name, shade=1.0):
        layer = spr.copy()
        layer[..., :3] = (layer[..., :3] * shade).astype(np.uint8)
        layer[~mask] = 0
        Image.fromarray(layer).save(out / name)

    save(solid & (clump == 0), "trunk.png")
    # what you see through a gap between two clumps: the same leaves, darker, pulled in 2 px from the outline
    save((clump > 0) & ndimage.binary_erosion(solid, iterations=2), "inside.png", shade=0.55)
    ids = [k for k in range(1, clump.max() + 1) if (clump == k).any()]
    for n, k in enumerate(ids):
        save(clump == k, f"clump_{n:02d}.png")
    return len(ids)


if __name__ == "__main__":
    print(split_tree(sys.argv[1], sys.argv[2], *[float(v) for v in sys.argv[3:]]), "clumps")
