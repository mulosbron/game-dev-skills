// Three.js Shading Language (TSL) — Animated Noise Lava Material
import * as THREE from 'three/webgpu';
import { time, uv, positionLocal, sin, cos, mix, vec3, float } from 'three/tsl';

export function createAnimatedNoiseLavaMaterial() {
  const mat = new THREE.MeshPhysicalNodeMaterial();
  const p = positionLocal.mul(4.0);
  const wave = sin(p.x.add(time.mul(2.0))).mul(cos(p.y.sub(time.mul(1.5)))).mul(0.5).add(0.5);

  const darkCrust = vec3(0.08, 0.05, 0.06);
  const magmaCore = vec3(1.0, 0.28, 0.04);
  const hotYellow = vec3(1.0, 0.85, 0.2);

  mat.colorNode = mix(darkCrust, magmaCore, wave);
  mat.emissiveNode = mix(vec3(0.0), hotYellow, wave.pow(2.5)).mul(2.2);
  mat.roughnessNode = mix(float(0.85), float(0.25), wave);
  mat.metalnessNode = float(0.1);
  return mat;
}
