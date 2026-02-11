#!/usr/bin/env node
/**
 * Gera favicon e ícones PWA a partir de alcahub-logo.png
 * Requer: npm install --save-dev sharp
 * Uso: node scripts/generate-icons.cjs
 */
const fs = require('fs');
const path = require('path');

const PUBLIC = path.join(__dirname, '..', 'public');
const LOGO = path.join(PUBLIC, 'alcahub-logo.png');

const sizes = [
  { name: 'favicon-16.png', size: 16 },
  { name: 'favicon-32.png', size: 32 },
  { name: 'icon-192.png', size: 192 },
  { name: 'icon-512.png', size: 512 },
];

async function main() {
  let sharp;
  try {
    sharp = require('sharp');
  } catch {
    console.error('Instale sharp: npm install --save-dev sharp');
    process.exit(1);
  }

  if (!fs.existsSync(LOGO)) {
    console.error('Logo não encontrada:', LOGO);
    process.exit(1);
  }

  const buffer = await sharp(LOGO)
    .resize(512, 512)
    .png()
    .toBuffer();

  for (const { name, size } of sizes) {
    const out = path.join(PUBLIC, name);
    const isPwa = size >= 192;

    if (isPwa) {
      // PWA: fundo sólido escuro (#0f172a) para boa legibilidade em home screens
      const logoResized = await sharp(buffer).resize(size, size).png().toBuffer();
      const bg = await sharp({
        create: {
          width: size,
          height: size,
          channels: 4,
          background: { r: 15, g: 23, b: 42, alpha: 1 },
        },
      })
        .png()
        .toBuffer();
      await sharp(bg)
        .composite([{ input: logoResized, top: 0, left: 0 }])
        .toFile(out);
    } else {
      await sharp(buffer).resize(size, size).png().toFile(out);
    }
    console.log('Gerado:', name);
  }

  console.log('Ícones gerados com sucesso.');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
