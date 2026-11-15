// Three.js Shading Language (TSL) — Physical Crystal Glass Material
import * as THREE from 'three/webgpu';
import { normalView, positionViewDirection, dot, clamp, pow, mix, vec3, float } from 'three/tsl';

export function createCrystalGlassMaterial() {
  const mat = new THREE.MeshPhysicalNodeMaterial({ transparent: true });
  const fresnel = pow(clamp(float(1.0).sub(dot(normalView, positionViewDirection)), 0.0, 1.0), 3.0);

  mat.colorNode = mix(vec3(0.15, 0.65, 1.0), vec3(0.75, 0.35, 1.0), fresnel);
  mat.transmissionNode = float(0.92);
  mat.ior = 1.52;
  mat.thicknessNode = float(0.6);
  mat.roughnessNode = float(0.06);
  mat.clearcoatNode = float(1.0);
  mat.emissiveNode = vec3(0.1, 0.4, 0.9).mul(fresnel.mul(0.8));
  return mat;
}
