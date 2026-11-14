// Carimbo da interface gerada: hash do codigo-fonte (fins de linha normalizados) gravado em dist/build-stamp.json.
// O app carrega ui/dist do repositorio; a CI confere se essa dist foi gerada a partir do codigo atual.
//   node scripts/stamp.mjs write   (depois do vite build)
//   node scripts/stamp.mjs check   (falha se o codigo mudou e a dist nao foi gerada de novo)
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const INPUTS = ["src", "index.html", "mini.html", "package-lock.json", "vite.config.ts", "tsconfig.json"];
const SKIP = /\.test\.tsx?$/;

function files(path) {
  const st = statSync(path);
  if (!st.isDirectory()) return [path];
  return readdirSync(path).flatMap((name) => files(join(path, name)));
}

function sourceHash() {
  const hash = createHash("sha256");
  const all = INPUTS.flatMap((p) => files(join(root, p)))
    .filter((f) => !SKIP.test(f))
    .map((f) => [relative(root, f).replaceAll("\\", "/"), f])
    .sort(([a], [b]) => a.localeCompare(b));
  for (const [rel, abs] of all) {
    hash.update(rel);
    hash.update(readFileSync(abs, "utf8").replace(/\r\n/g, "\n"));
  }
  return hash.digest("hex");
}

const stampFile = join(root, "dist", "build-stamp.json");
const mode = process.argv[2];
if (mode === "write") {
  writeFileSync(stampFile, JSON.stringify({ source_sha256: sourceHash() }, null, 2) + "\n");
  console.log("carimbo gravado");
} else if (mode === "check") {
  let stamped = "";
  try {
    stamped = JSON.parse(readFileSync(stampFile, "utf8")).source_sha256;
  } catch {
    /* sem carimbo */
  }
  if (stamped !== sourceHash()) {
    console.error("ui/dist nao corresponde ao codigo: rode 'npm run build' em ui/ e commite a dist.");
    process.exit(1);
  }
  console.log("ui/dist em dia");
} else {
  console.error("uso: node scripts/stamp.mjs write|check");
  process.exit(2);
}
