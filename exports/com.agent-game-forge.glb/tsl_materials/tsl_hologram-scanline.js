// Three.js Shading Language (TSL) — Sci-Fi Hologram Material
import * as THREE from 'three/webgpu';
import { time, positionWorld, normalView, positionViewDirection, dot, sin, pow, clamp, vec3, float } from 'three/tsl';

export function createHologramMaterial() {
  const mat = new THREE.MeshPhysicalNodeMaterial({ transparent: true, depthWrite: false });
  const scanline = sin(positionWorld.y.mul(45.0).sub(time.mul(8.0))).mul(0.5).add(0.5);
  const rim = pow(clamp(float(1.0).sub(dot(normalView, positionViewDirection)), 0.0, 1.0), 2.2);

  const holoCyan = vec3(0.1, 0.88, 1.0);
  mat.colorNode = holoCyan;
  mat.emissiveNode = holoCyan.mul(rim.add(scanline.mul(0.45))).mul(1.8);
  mat.opacityNode = clamp(rim.add(scanline.mul(0.25)), 0.15, 0.95);
  return mat;
}
