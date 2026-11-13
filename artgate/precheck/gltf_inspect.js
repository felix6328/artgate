#!/usr/bin/env node
/**
 * 用官方 glTF-Transform inspect() 抽取面数、贴图尺寸、材质通道。
 * 数值类结论必须来自这里（或同等确定性工具），禁止模型口算。
 */
const path = require('path');
const { NodeIO } = require('@gltf-transform/core');
const { ALL_EXTENSIONS } = require('@gltf-transform/extensions');
const { inspect } = require('@gltf-transform/functions');

function jsonSafe(key, value) {
  if (typeof value === 'bigint') return Number(value);
  if (value instanceof Map) return Object.fromEntries(value);
  if (typeof value === 'undefined') return null;
  if (value && value.byteLength && !Array.isArray(value) && typeof value === 'object' && value.constructor && value.constructor.name === 'Uint8Array') {
    return { byteLength: value.byteLength };
  }
  return value;
}

async function main() {
  const file = process.argv[2];
  if (!file) {
    console.error(JSON.stringify({ ok: false, error: 'usage: gltf_inspect.js <file>' }));
    process.exit(2);
  }
  const abs = path.resolve(file);
  try {
    const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
    const doc = await io.read(abs);
    const report = inspect(doc);
    process.stdout.write(JSON.stringify({ ok: true, report }, jsonSafe));
  } catch (err) {
    process.stdout.write(JSON.stringify({
      ok: false,
      tool_failed: true,
      error: String(err && err.message ? err.message : err),
    }));
    process.exit(0);
  }
}

main();
