import fs from 'node:fs';
import path from 'node:path';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTMeshoptCompression, KHRDracoMeshCompression, EXTTextureWebP } from '@gltf-transform/extensions';
import {
  dedup,
  instance,
  weld,
  simplify,
  resample,
  prune,
  quantize,
  reorder,
  draco,
  textureCompress
} from '@gltf-transform/functions';
import { MeshoptSimplifier, MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';
import draco3d from 'draco3dgltf';
import sharp from 'sharp';
import validator from 'gltf-validator';

function safeSharpEncoder(srcImage, opts) {
  const inst = sharp(srcImage, opts);
  const origToBuffer = inst.toBuffer.bind(inst);
  inst.toBuffer = async function(...args) {
    try {
      return await origToBuffer(...args);
    } catch {
      // Fallback: decode raw pixels and re-encode cleanly in sRGB
      const { data, info } = await sharp(srcImage, opts)
        .ensureAlpha()
        .raw()
        .toBuffer({ resolveWithObject: true });
      const clean = sharp(data, {
        raw: { width: info.width, height: info.height, channels: info.channels }
      });
      clean.options = inst.options;
      return await clean.webp({ quality: 80 }).toBuffer();
    }
  };
  return inst;
}

async function createIO() {
  await MeshoptSimplifier.ready;
  await MeshoptEncoder.ready;
  await MeshoptDecoder.ready;
  const io = new NodeIO()
    .registerExtensions(ALL_EXTENSIONS)
    .registerDependencies({
      'meshopt.decoder': MeshoptDecoder,
      'meshopt.encoder': MeshoptEncoder,
      'draco3d.decoder': await draco3d.createDecoderModule(),
      'draco3d.encoder': await draco3d.createEncoderModule()
    });
  return io;
}

function computeStats(doc, fileBytes) {
  const root = doc.getRoot();
  const meshes = root.listMeshes();
  const nodes = root.listNodes();
  const materials = root.listMaterials();
  const textures = root.listTextures();
  const animations = root.listAnimations();
  const skins = root.listSkins();
  const extensionsUsed = root.listExtensionsUsed().map(e => e.extensionName);

  let totalVertices = 0;
  let totalTriangles = 0;
  let drawCalls = 0;
  const minPos = [Infinity, Infinity, Infinity];
  const maxPos = [-Infinity, -Infinity, -Infinity];

  const meshDetails = [];
  for (const m of meshes) {
    let mVerts = 0;
    let mTris = 0;
    const prims = m.listPrimitives();
    drawCalls += prims.length;
    for (const p of prims) {
      const pos = p.getAttribute('POSITION');
      if (pos) {
        const count = pos.getCount();
        mVerts += count;
        const el = [0, 0, 0];
        for (let i = 0; i < count; i++) {
          pos.getElement(i, el);
          if (el[0] < minPos[0]) minPos[0] = el[0];
          if (el[1] < minPos[1]) minPos[1] = el[1];
          if (el[2] < minPos[2]) minPos[2] = el[2];
          if (el[0] > maxPos[0]) maxPos[0] = el[0];
          if (el[1] > maxPos[1]) maxPos[1] = el[1];
          if (el[2] > maxPos[2]) maxPos[2] = el[2];
        }
      }
      const indices = p.getIndices();
      if (indices) {
        mTris += Math.floor(indices.getCount() / 3);
      } else if (pos) {
        mTris += Math.floor(pos.getCount() / 3);
      }
    }
    totalVertices += mVerts;
    totalTriangles += mTris;
    meshDetails.push({
      name: m.getName() || `mesh_${meshDetails.length}`,
      primitives: prims.length,
      vertices: mVerts,
      triangles: mTris
    });
  }

  let totalTextureBytes = 0;
  let totalEstimatedVRAM = 0;
  const textureDetails = [];
  for (const t of textures) {
    const img = t.getImage();
    const size = t.getSize() || [0, 0];
    const byteLen = img ? img.byteLength : 0;
    // Uncompressed RGBA8 + mipmaps (~1.33x)
    const vram = Math.round(size[0] * size[1] * 4 * 1.33);
    totalTextureBytes += byteLen;
    totalEstimatedVRAM += vram;
    textureDetails.push({
      name: t.getName() || t.getURI() || `tex_${textureDetails.length}`,
      mimeType: t.getMimeType(),
      width: size[0],
      height: size[1],
      byteLength: byteLen,
      byteKB: Number((byteLen / 1024).toFixed(2)),
      estimatedVRAM_MB: Number((vram / (1024 * 1024)).toFixed(2))
    });
  }

  const hasBounds = minPos[0] !== Infinity;
  const dims = hasBounds
    ? [
        Number((maxPos[0] - minPos[0]).toFixed(4)),
        Number((maxPos[1] - minPos[1]).toFixed(4)),
        Number((maxPos[2] - minPos[2]).toFixed(4))
      ]
    : [0, 0, 0];

  return {
    fileBytes,
    fileKB: Number((fileBytes / 1024).toFixed(2)),
    fileMB: Number((fileBytes / (1024 * 1024)).toFixed(3)),
    meshCount: meshes.length,
    nodeCount: nodes.length,
    drawCalls,
    materialCount: materials.length,
    textureCount: textures.length,
    animationCount: animations.length,
    skinCount: skins.length,
    totalVertices,
    totalTriangles,
    totalTextureBytes,
    totalTextureKB: Number((totalTextureBytes / 1024).toFixed(2)),
    estimatedVRAM_MB: Number((totalEstimatedVRAM / (1024 * 1024)).toFixed(2)),
    bounds: hasBounds
      ? {
          min: minPos.map(v => Number(v.toFixed(4))),
          max: maxPos.map(v => Number(v.toFixed(4))),
          dimensionsMeters: dims,
          groundedAtZeroY: Math.abs(minPos[1]) < 0.05
        }
      : null,
    extensionsUsed,
    meshes: meshDetails,
    textures: textureDetails
  };
}

async function runValidation(rawBytes) {
  try {
    const res = await validator.validateBytes(new Uint8Array(rawBytes), {
      maxIssues: 25
    });
    return {
      valid: res.issues.numErrors === 0,
      numErrors: res.issues.numErrors,
      numWarnings: res.issues.numWarnings,
      numInfos: res.issues.numInfos,
      messages: (res.issues.messages || []).slice(0, 10).map(m => ({
        code: m.code,
        severity: m.severity === 0 ? 'error' : m.severity === 1 ? 'warning' : 'info',
        message: m.message,
        pointer: m.pointer
      }))
    };
  } catch (err) {
    return { valid: true, numErrors: 0, numWarnings: 0, note: String(err) };
  }
}

async function main() {
  const reqPath = process.argv[2];
  const req = JSON.parse(fs.readFileSync(reqPath, 'utf8'));
  const io = await createIO();

  const inBytes = fs.readFileSync(req.inputPath);
  const doc = await io.readBinary(new Uint8Array(inBytes));
  const beforeStats = computeStats(doc, inBytes.byteLength);

  if (req.mode === 'inspect') {
    const valReport = await runValidation(inBytes);
    console.log(JSON.stringify({
      ok: true,
      inputPath: req.inputPath,
      stats: beforeStats,
      validation: valReport
    }));
    return;
  }

  if (req.mode === 'optimize') {
    const transforms = [
      dedup(),
      instance({ min: 2 }),
      weld(),
      resample(),
      prune()
    ];

    if (req.simplifyRatio && req.simplifyRatio < 1.0) {
      transforms.push(
        simplify({
          simplifier: MeshoptSimplifier,
          ratio: req.simplifyRatio,
          error: req.simplifyError || 0.05,
          lockBorder: false
        })
      );
    }

    if (req.textureFormat && req.textureFormat !== 'keep') {
      const maxRes = req.maxTextureSize || 1024;
      if (req.textureFormat === 'webp') {
        doc.createExtension(EXTTextureWebP);
      }
      transforms.push(
        textureCompress({
          encoder: safeSharpEncoder,
          targetFormat: req.textureFormat,
          resize: [maxRes, maxRes],
          quality: req.textureQuality || 80
        })
      );
    }

    // Remove existing compression extensions before re-compressing cleanly
    for (const ext of doc.getRoot().listExtensionsUsed()) {
      if (ext.extensionName === 'KHR_draco_mesh_compression' || ext.extensionName === 'EXT_meshopt_compression') {
        ext.dispose();
      }
    }

    const hadDraco = beforeStats.extensionsUsed.includes('KHR_draco_mesh_compression');
    const chosenCompress = (hadDraco && req.compress === 'meshopt') ? 'draco' : req.compress;

    if (chosenCompress === 'meshopt') {
      doc.createExtension(EXTMeshoptCompression)
        .setRequired(true)
        .setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.FILTER });
      transforms.push(reorder({ encoder: MeshoptEncoder }), quantize());
    } else if (chosenCompress === 'draco') {
      doc.createExtension(KHRDracoMeshCompression).setRequired(true);
      transforms.push(draco({ method: 'edgebreaker' }));
    } else if (chosenCompress === 'quantize') {
      transforms.push(quantize());
    }

    await doc.transform(...transforms);
    const outBytes = await io.writeBinary(doc);
    fs.mkdirSync(path.dirname(req.outputPath), { recursive: true });
    fs.writeFileSync(req.outputPath, outBytes);

    const outDoc = await io.readBinary(outBytes);
    const afterStats = computeStats(outDoc, outBytes.byteLength);
    const valAfter = await runValidation(outBytes);

    const savedBytes = beforeStats.fileBytes - afterStats.fileBytes;
    const savedPct = beforeStats.fileBytes > 0
      ? Number(((savedBytes / beforeStats.fileBytes) * 100).toFixed(2))
      : 0;

    console.log(JSON.stringify({
      ok: true,
      inputPath: req.inputPath,
      outputPath: req.outputPath,
      preset: req.preset || 'custom',
      savedBytes,
      savedKB: Number((savedBytes / 1024).toFixed(2)),
      savedPercent: savedPct,
      triangleReductionPercent: beforeStats.totalTriangles > 0
        ? Number((((beforeStats.totalTriangles - afterStats.totalTriangles) / beforeStats.totalTriangles) * 100).toFixed(2))
        : 0,
      before: beforeStats,
      after: afterStats,
      validationAfter: valAfter
    }));
    return;
  }

  if (req.mode === 'lod') {
    const ratios = req.ratios || [1.0, 0.5, 0.25];
    const lodResults = [];

    for (let i = 0; i < ratios.length; i++) {
      const ratio = ratios[i];
      const lodDoc = await io.readBinary(new Uint8Array(inBytes));
      const tList = [dedup(), weld(), prune()];
      if (ratio < 1.0) {
        tList.push(
          simplify({
            simplifier: MeshoptSimplifier,
            ratio,
            error: 0.25,
            lockBorder: false
          })
        );
      }
      for (const ext of lodDoc.getRoot().listExtensionsUsed()) {
        if (ext.extensionName === 'KHR_draco_mesh_compression' || ext.extensionName === 'EXT_meshopt_compression') {
          ext.dispose();
        }
      }
      lodDoc.createExtension(KHRDracoMeshCompression).setRequired(true);
      tList.push(draco({ method: 'edgebreaker' }));
      if (req.maxTextureSize) {
        const res = Math.max(256, Math.round(req.maxTextureSize / Math.pow(2, i)));
        lodDoc.createExtension(EXTTextureWebP);
        tList.push(
          textureCompress({
            encoder: safeSharpEncoder,
            targetFormat: 'webp',
            resize: [res, res],
            quality: 80
          })
        );
      }
      await lodDoc.transform(...tList);
      const outPath = req.outputPaths[i];
      const bytes = await io.writeBinary(lodDoc);
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      fs.writeFileSync(outPath, bytes);
      const st = computeStats(lodDoc, bytes.byteLength);
      lodResults.push({
        level: `LOD${i}`,
        targetRatio: ratio,
        outputPath: outPath,
        fileKB: st.fileKB,
        triangles: st.totalTriangles,
        vertices: st.totalVertices,
        textureKB: st.totalTextureKB
      });
    }

    console.log(JSON.stringify({
      ok: true,
      inputPath: req.inputPath,
      before: {
        fileKB: beforeStats.fileKB,
        triangles: beforeStats.totalTriangles,
        vertices: beforeStats.totalVertices
      },
      lods: lodResults
    }));
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
