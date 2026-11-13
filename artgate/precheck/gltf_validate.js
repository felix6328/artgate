#!/usr/bin/env node
/**
 * 调用官方 Khronos gltf-validator，并正确解析 GLB 的外部贴图 URI。
 * 若不提供 externalResourceFunction，Kenney 这类「GLB + 外部 colormap.png」
 * 会被误报 IO_ERROR（error），那是调用方式的问题，不是资产不合规。
 */
const fs = require('fs');
const path = require('path');
const validator = require('gltf-validator');

async function main() {
  const file = process.argv[2];
  if (!file) {
    console.error(JSON.stringify({ ok: false, error: 'usage: gltf_validate.js <file>' }));
    process.exit(2);
  }
  const abs = path.resolve(file);
  const dir = path.dirname(abs);
  const buf = fs.readFileSync(abs);
  try {
    const result = await validator.validateBytes(new Uint8Array(buf), {
      uri: path.basename(abs),
      externalResourceFunction: (uri) => {
        const cleaned = decodeURIComponent(String(uri).split('?')[0]);
        const p = path.resolve(dir, cleaned);
        if (!fs.existsSync(p)) {
          return Promise.reject(new Error('external resource not found: ' + cleaned));
        }
        return Promise.resolve(fs.readFileSync(p));
      },
    });
    process.stdout.write(JSON.stringify({ ok: true, result }));
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
