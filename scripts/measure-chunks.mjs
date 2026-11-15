// Mide el tamaño de los chunks JS de Next.js (.next/static/chunks) y
// busca en qué archivo aparece cada texto indicado como argumento.
// Uso (desde uis/backoffice, después de npm run build):
//   node ../../scripts/measure-chunks.mjs "texto 1" "texto 2"
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { gzipSync } from "node:zlib";

const root = join(process.cwd(), ".next", "static", "chunks");
const markers = process.argv.slice(2);

function walk(dir) {
  const files = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      files.push(...walk(full));
    } else if (name.endsWith(".js")) {
      files.push(full);
    }
  }
  return files;
}

let files;
try {
  files = walk(root);
} catch {
  console.error(`No existe ${root}. Ejecuta antes npm run build en uis/backoffice.`);
  process.exit(1);
}

const rows = files.map((file) => {
  const content = readFileSync(file);
  return {
    name: relative(root, file),
    raw: content.length,
    gzip: gzipSync(content).length,
    text: content.toString("utf8"),
  };
});

const totalRaw = rows.reduce((sum, row) => sum + row.raw, 0);
const totalGzip = rows.reduce((sum, row) => sum + row.gzip, 0);

console.log(`Archivos JS: ${rows.length}`);
console.log(`Total sin comprimir: ${totalRaw} B`);
console.log(`Total gzip: ${totalGzip} B`);

console.log("\nLos 8 más grandes (gzip):");
for (const row of [...rows].sort((a, b) => b.gzip - a.gzip).slice(0, 8)) {
  console.log(`  ${row.name}  raw=${row.raw} B  gzip=${row.gzip} B`);
}

if (markers.length > 0) {
  console.log("\nTextos buscados:");
  for (const marker of markers) {
    const hits = rows.filter((row) => row.text.includes(marker));
    if (hits.length === 0) {
      console.log(`  "${marker}": no aparece en ningún chunk`);
    } else {
      for (const row of hits) {
        console.log(`  "${marker}": ${row.name}  (gzip=${row.gzip} B)`);
      }
    }
  }
}
