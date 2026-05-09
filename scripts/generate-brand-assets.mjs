/**
 * Generate all transparent PNG brand assets from the Canva G mark.
 *
 * Source: public/brand/gridar-mark-canva.png (white background)
 * We strip the white via per-pixel alpha threshold (smooth ramp on near-white
 * pixels so anti-aliased edges fade out cleanly), then resize to every size we
 * need. The resulting master 1024px PNG is reused for all downscales for a
 * sharper result than re-rendering from the source each time.
 *
 * Run: node scripts/generate-brand-assets.mjs
 */
import sharp from "sharp";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const SRC = resolve(ROOT, "public/brand/gridar-mark-canva.png");

async function ensureDir(p) {
  await mkdir(dirname(p), { recursive: true });
}

/**
 * Read an opaque PNG and return a transparent buffer where near-white pixels
 * (the Canva white background) are made transparent with a smooth ramp.
 */
async function stripWhiteBackground(srcPath) {
  const { data, info } = await sharp(srcPath)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  // Tunables. Pixels with min(R,G,B) >= HIGH are pure bg → fully transparent.
  // Pixels with min(R,G,B) <= LOW are content → fully opaque.
  // Between LOW and HIGH: smooth ramp on alpha.
  const HIGH = 250;
  const LOW = 215;

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const minCh = Math.min(r, g, b);
    if (minCh >= HIGH) {
      data[i + 3] = 0;
    } else if (minCh > LOW) {
      const t = 1 - (minCh - LOW) / (HIGH - LOW);
      data[i + 3] = Math.round(255 * t);
    }
    // else: leave alpha at 255 (content pixel)
  }

  return sharp(data, {
    raw: { width: info.width, height: info.height, channels: 4 },
  })
    .png({ compressionLevel: 9, palette: false })
    .toBuffer();
}

async function renderSize(masterBuffer, size, outPath) {
  await ensureDir(outPath);
  await sharp(masterBuffer)
    .resize(size, size, {
      fit: "contain",
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png({ compressionLevel: 9 })
    .toFile(outPath);
  console.log(`  ${size}x${size} -> ${outPath.replace(ROOT + "\\", "").replace(ROOT + "/", "")}`);
}

async function buildIco(masterBuffer) {
  const sizes = [16, 32, 48];
  const pngs = await Promise.all(
    sizes.map(async (s) => {
      const buf = await sharp(masterBuffer)
        .resize(s, s, {
          fit: "contain",
          background: { r: 0, g: 0, b: 0, alpha: 0 },
        })
        .png({ compressionLevel: 9 })
        .toBuffer();
      return { size: s, buf };
    }),
  );

  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(pngs.length, 4);

  const entries = [];
  let offset = 6 + 16 * pngs.length;
  for (const { size, buf } of pngs) {
    const entry = Buffer.alloc(16);
    entry.writeUInt8(size === 256 ? 0 : size, 0);
    entry.writeUInt8(size === 256 ? 0 : size, 1);
    entry.writeUInt8(0, 2);
    entry.writeUInt8(0, 3);
    entry.writeUInt16LE(1, 4);
    entry.writeUInt16LE(32, 6);
    entry.writeUInt32LE(buf.length, 8);
    entry.writeUInt32LE(offset, 12);
    entries.push(entry);
    offset += buf.length;
  }
  const ico = Buffer.concat([header, ...entries, ...pngs.map((p) => p.buf)]);
  const out = resolve(ROOT, "public/favicon.ico");
  await writeFile(out, ico);
  console.log(`  multi-res 16/32/48 -> public/favicon.ico`);
}

async function main() {
  console.log("Stripping white background from", SRC);
  const transparentBuffer = await stripWhiteBackground(SRC);

  // Save the master high-res transparent version. Other sizes downscale from it.
  const master = resolve(ROOT, "public/brand/gridar-mark-master.png");
  await ensureDir(master);
  await sharp(transparentBuffer)
    .resize(1024, 1024, {
      fit: "contain",
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png({ compressionLevel: 9 })
    .toFile(master);
  const masterBuffer = await sharp(master).toBuffer();
  console.log(`  1024x1024 -> public/brand/gridar-mark-master.png (transparent master)`);

  // Favicons
  await renderSize(masterBuffer, 16, resolve(ROOT, "public/favicon-16.png"));
  await renderSize(masterBuffer, 32, resolve(ROOT, "public/favicon-32.png"));
  await renderSize(masterBuffer, 48, resolve(ROOT, "public/favicon-48.png"));

  // iOS / Android touch icon
  await renderSize(masterBuffer, 180, resolve(ROOT, "public/apple-touch-icon.png"));

  // PWA manifest icons
  await renderSize(masterBuffer, 192, resolve(ROOT, "public/icons/icon-192.png"));
  await renderSize(masterBuffer, 512, resolve(ROOT, "public/icons/icon-512.png"));

  // Brand assets for email signatures, slides, social, etc.
  await renderSize(masterBuffer, 256, resolve(ROOT, "public/brand/gridar-mark-256.png"));
  await renderSize(masterBuffer, 512, resolve(ROOT, "public/brand/gridar-mark-512.png"));
  await renderSize(masterBuffer, 1024, resolve(ROOT, "public/brand/gridar-mark-1024.png"));

  // Multi-res ICO
  await buildIco(masterBuffer);

  console.log("\nDone.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
