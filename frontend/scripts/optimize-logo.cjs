// Run from frontend/: node scripts/optimize-logo.cjs
const sharp = require('sharp');

(async () => {
  for (const width of [240, 480]) {
    const file = `public/alcahub-logo-v1-${width}.webp`;
    const info = await sharp('public/alcahub-logo.png')
      .resize({ width }).webp({ quality: 85, alphaQuality: 100 }).toFile(file);
    console.log(`${file}: ${info.width}x${info.height}, ${info.size} bytes`);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
