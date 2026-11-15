import { Vector3 } from 'three';
export function frameOf(forward, up) {
    const z = (forward ?? new Vector3(0, 0, 1)).clone().normalize();
    const hint = (up ?? new Vector3(0, 1, 0)).clone();
    hint.addScaledVector(z, -hint.dot(z));
    if (hint.lengthSq() < 1e-10) {
        hint.set(Math.abs(z.y) < 0.9 ? 0 : 1, Math.abs(z.y) < 0.9 ? 1 : 0, 0);
        hint.addScaledVector(z, -hint.dot(z));
    }
    const y = hint.normalize();
    const x = y.clone().cross(z).normalize();
    return { right: x, up: y, forward: z };
}
function boundsOf(center, extent) {
    return { min: [center.x - extent, center.y - extent, center.z - extent], max: [center.x + extent, center.y + extent, center.z + extent] };
}
export function ellipsoidShape(id, label, center, radii, frame, taper, bone, paint, detail) {
    if (!radii.every(value => Number.isFinite(value) && value > 0))
        throw new Error('Sculpt ellipsoid ' + label + ' has a collapsed radius');
    if (!(Math.abs(taper) < 0.95))
        throw new Error('Sculpt ellipsoid ' + label + ' taper must stay inside -0.95..0.95');
    const [rx, ry, rz] = radii;
    const cx = center.x, cy = center.y, cz = center.z;
    const ax = frame.right, ay = frame.up, az = frame.forward;
    const smallest = Math.min(rx, ry, rz) * (1 - Math.abs(taper));
    const extent = Math.max(rx, ry, rz) * (1 + Math.abs(taper));
    return {
        id, label, bone, paint, detail, ...boundsOf(center, extent),
        distance(x, y, z) {
            const dx = x - cx, dy = y - cy, dz = z - cz;
            const lz = dx * az.x + dy * az.y + dz * az.z;
            const grow = 1 + taper * Math.max(-1, Math.min(1, lz / rz));
            const lx = (dx * ax.x + dy * ax.y + dz * ax.z) / grow;
            const ly = (dx * ay.x + dy * ay.y + dz * ay.z) / grow;
            const qx = lx / rx, qy = ly / ry, qz = lz / rz;
            const k0 = Math.sqrt(qx * qx + qy * qy + qz * qz);
            const px = qx / rx, py = qy / ry, pz = qz / rz;
            const k1 = Math.sqrt(px * px + py * py + pz * pz);
            if (k1 < 1e-12)
                return -smallest;
            return k0 * (k0 - 1) / k1 * Math.min(1, grow);
        },
    };
}
export function coneShape(id, label, a, b, r1, r2, bone, paint, detail) {
    if (!(r1 > 0) || !(r2 > 0))
        throw new Error('Sculpt limb ' + label + ' has a collapsed radius');
    const bax = b.x - a.x, bay = b.y - a.y, baz = b.z - a.z;
    const l2 = bax * bax + bay * bay + baz * baz;
    const rr = r1 - r2;
    if (!(Math.sqrt(l2) > Math.abs(rr) + 1e-6))
        throw new Error('Sculpt limb ' + label + ' is shorter than its change in radius');
    const a2 = l2 - rr * rr, il2 = 1 / l2;
    const ax = a.x, ay = a.y, az = a.z;
    const minX = Math.min(a.x - r1, b.x - r2), minY = Math.min(a.y - r1, b.y - r2), minZ = Math.min(a.z - r1, b.z - r2);
    const maxX = Math.max(a.x + r1, b.x + r2), maxY = Math.max(a.y + r1, b.y + r2), maxZ = Math.max(a.z + r1, b.z + r2);
    return {
        id, label, bone, paint, detail, min: [minX, minY, minZ], max: [maxX, maxY, maxZ],
        distance(x, y, z) {
            const pax = x - ax, pay = y - ay, paz = z - az;
            const yy = pax * bax + pay * bay + paz * baz;
            const zz = yy - l2;
            const qx = pax * l2 - bax * yy, qy = pay * l2 - bay * yy, qz = paz * l2 - baz * yy;
            const x2 = qx * qx + qy * qy + qz * qz;
            const y2 = yy * yy * l2, z2 = zz * zz * l2;
            const k = Math.sign(rr) * rr * rr * x2;
            if (Math.sign(zz) * a2 * z2 > k)
                return Math.sqrt(x2 + z2) * il2 - r2;
            if (Math.sign(yy) * a2 * y2 < k)
                return Math.sqrt(x2 + y2) * il2 - r1;
            return (Math.sqrt(x2 * a2 * il2) + yy * rr) * il2 - r1;
        },
    };
}
function smin(a, b, k) {
    if (k <= 0)
        return Math.min(a, b);
    const h = Math.max(k - Math.abs(a - b), 0) / k;
    return Math.min(a, b) - h * h * k * 0.25;
}
function smax(a, b, k) {
    return -smin(-a, -b, k);
}
export const FAR = 1e9;
export class SculptField {
    root;
    shapes;
    floor;
    overlays;
    owner = null;
    active = null;
    buckets = [];
    bucketSize = 0;
    bucketOrigin = [0, 0, 0];
    bucketCount = [0, 0, 0];
    constructor(root, shapes, floor, overlays = []) {
        this.root = root;
        this.shapes = shapes;
        this.floor = floor;
        this.overlays = overlays;
    }
    restrict(active) { this.active = active; }
    accelerate(size, reachOf) {
        const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
        for (const shape of this.shapes)
            for (let axis = 0; axis < 3; axis++) {
                lo[axis] = Math.min(lo[axis], shape.min[axis] - reachOf(shape));
                hi[axis] = Math.max(hi[axis], shape.max[axis] + reachOf(shape));
            }
        if (!Number.isFinite(lo[0]))
            return;
        const ids = this.shapes.reduce((most, shape) => Math.max(most, shape.id + 1), 0);
        this.bucketSize = size;
        this.bucketOrigin = lo;
        this.bucketCount = lo.map((value, axis) => Math.max(1, Math.ceil((hi[axis] - value) / size)));
        const [nx, ny, nz] = this.bucketCount;
        this.buckets = new Array(nx * ny * nz).fill(null);
        for (const shape of this.shapes) {
            const reach = reachOf(shape);
            const from = [0, 1, 2].map(axis => Math.max(0, Math.floor((shape.min[axis] - reach - lo[axis]) / size)));
            const to = [0, 1, 2].map(axis => Math.min(this.bucketCount[axis] - 1, Math.floor((shape.max[axis] + reach - lo[axis]) / size)));
            for (let k = from[2]; k <= to[2]; k++)
                for (let j = from[1]; j <= to[1]; j++)
                    for (let i = from[0]; i <= to[0]; i++) {
                        const index = (k * ny + j) * nx + i;
                        const bucket = this.buckets[index] ?? new Uint8Array(ids);
                        bucket[shape.id] = 1;
                        this.buckets[index] = bucket;
                    }
        }
    }
    nearby(x, y, z) {
        if (!this.bucketSize)
            return null;
        const i = Math.floor((x - this.bucketOrigin[0]) / this.bucketSize), j = Math.floor((y - this.bucketOrigin[1]) / this.bucketSize), k = Math.floor((z - this.bucketOrigin[2]) / this.bucketSize);
        const [nx, ny, nz] = this.bucketCount;
        if (i < 0 || j < 0 || k < 0 || i >= nx || j >= ny || k >= nz)
            return null;
        return this.buckets[(k * ny + j) * nx + i] ?? null;
    }
    value(x, y, z) {
        if (!this.active && this.bucketSize) {
            const bucket = this.nearby(x, y, z);
            if (bucket) {
                this.active = bucket;
                const value = this.node(this.root, x, y, z);
                this.active = null;
                this.owner = this.found;
                return this.floor === null ? value : Math.max(value, this.floor - y);
            }
        }
        const value = this.node(this.root, x, y, z);
        this.owner = this.found;
        return this.floor === null ? value : Math.max(value, this.floor - y);
    }
    found = null;
    node(node, x, y, z) {
        let value = FAR;
        let nearest = FAR;
        let owner = null;
        for (const shape of node.shapes) {
            if (this.active && !this.active[shape.id])
                continue;
            const d = shape.distance(x, y, z);
            if (d < nearest) {
                nearest = d;
                owner = shape;
            }
            value = smin(value, d, node.blend);
        }
        for (const carve of node.carves) {
            if (this.active && !this.active[carve.shape.id])
                continue;
            const d = -carve.shape.distance(x, y, z);
            if (d > value)
                owner = carve.shape;
            value = smax(value, d, carve.blend);
        }
        if (!node.children.length) {
            this.found = owner;
            return value;
        }
        let best = value;
        let bestOwner = owner;
        for (const child of node.children) {
            const branch = this.node(child, x, y, z);
            if (branch >= FAR * 0.5)
                continue;
            const joined = smin(value, branch, child.join);
            if (joined < best) {
                best = joined;
                bestOwner = branch < value ? this.found : owner;
            }
        }
        this.found = bestOwner;
        return best;
    }
    gradient(x, y, z, step, out) {
        out.set(this.value(x + step, y, z) - this.value(x - step, y, z), this.value(x, y + step, z) - this.value(x, y - step, z), this.value(x, y, z + step) - this.value(x, y, z - step));
        const length = out.length();
        return length > 1e-12 ? out.multiplyScalar(1 / length) : out.set(0, 1, 0);
    }
    project(point, step, limit) {
        const start = point.clone();
        const normal = new Vector3();
        for (let i = 0; i < 4; i++) {
            const d = this.value(point.x, point.y, point.z);
            if (Math.abs(d) < step * 0.02)
                break;
            this.gradient(point.x, point.y, point.z, step, normal);
            point.addScaledVector(normal, -d);
        }
        const moved = point.distanceTo(start);
        if (moved > limit)
            point.copy(start).lerp(point, limit / moved);
        return point;
    }
    ownerAt(x, y, z, skip) {
        this.value(x, y, z);
        let owner = this.owner;
        for (const overlay of this.overlays)
            if (!skip?.has(overlay) && overlay.distance(x, y, z) < 0)
                owner = overlay;
        if (!owner)
            throw new Error('Sculpt surface has no owning shape at ' + [x, y, z].map(v => v.toFixed(4)).join(','));
        return owner;
    }
}
