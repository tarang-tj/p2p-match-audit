// Run web/audit.js the way the browser does (a plain script setting a global), on a sample
// file, and print {case_id: {control: true|false|null}} as JSON. Used by the parity test.
// Usage: node scripts/run_browser_audit.mjs [web/data/sample.json]
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const src = await readFile(new URL("../web/audit.js", import.meta.url), "utf8");
const sample = JSON.parse(await readFile(process.argv[2] || "web/data/sample.json", "utf8"));
const ctx = vm.createContext({ Intl, Date, Set, Error, Boolean });
vm.runInContext(src, ctx);
const out = {};
for (const r of ctx.P2PAudit.run(sample)) out[r.id] = r.flags;
process.stdout.write(JSON.stringify(out));
