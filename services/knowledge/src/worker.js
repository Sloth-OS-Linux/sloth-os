// Sloth OS közös tudás: a gépek névtelenül jelentik, melyik beállítással indult el egy Windows-program,
// és ami sok gépen bevált, az összesítésbe kerül (a gépek a GitHubról olvassák, lásd README.md).
//
//   POST /v1/report   jelentések (legfeljebb 50 egyszerre), szigorú ellenőrzéssel
//   GET  /v1/export   az összesítés (csak az EXPORT_TOKEN-nel; a GitHub Action hívja)
//
// Csak engedélyezett beállítás kerülhet be (lásd ALLOWED_*): tetszőleges parancsot, környezeti változót
// vagy paramétert jelentésből nem lehet terjeszteni. A listák a sloth_exe/heal.py és diagnose.py
// értékeivel egyeznek; ha ott bővül, itt is kell.

const ALLOWED_LINES = new Set(["UMU-Proton", "GE-Proton"]);
const ALLOWED_PROFILES = new Set(["default", "nofsync", "wined3d"]);
const ALLOWED_GPUS = new Set(["amd", "nvidia", "intel", "other"]);
const ALLOWED_VERBS = new Set([
  "d3dcompiler_42", "d3dcompiler_43", "d3dcompiler_46", "d3dcompiler_47", "d3dx10", "d3dx11_42", "d3dx11_43",
  "d3dx9", "dotnet48", "gdiplus", "mf", "mfc42", "msxml3", "msxml4", "msxml6", "physx", "riched20", "vb6run",
  "vcrun2005", "vcrun2008", "vcrun2010", "vcrun2012", "vcrun2013", "vcrun2022", "xact", "xinput",
]);
const ALLOWED_ENV = new Set(["PROTON_USE_WINED3D"]);
const ALLOWED_ARGS = new Set(["--disable-gpu"]);

const MAX_BATCH = 50;
const MAX_BODY = 64 * 1024;
const DAILY_LIMIT = 500;      // jelentés / cím / nap
const MIN_MACHINES = 3;       // ennyi különböző gépen kell beválnia
const MIN_SUCCESS = 0.75;     // és a jelentések legalább ennyi része legyen sikeres

const HEX64 = /^[0-9a-f]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function sha256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Egy jelentés ellenőrzése és kanonikus alakja; null, ha bármi nem stimmel
function validate(r) {
  if (!r || typeof r !== "object") return null;
  const { machine, program, gpu, line, profile, fixes = [], outcome } = r;
  if (typeof machine !== "string" || !UUID.test(machine)) return null;
  if (typeof program !== "string" || !HEX64.test(program)) return null;
  if (!ALLOWED_GPUS.has(gpu) || !ALLOWED_LINES.has(line) || !ALLOWED_PROFILES.has(profile)) return null;
  if (outcome !== "worked" && outcome !== "failed") return null;
  if (!Array.isArray(fixes) || fixes.length > 10) return null;
  const clean = [];
  for (const fix of fixes) {
    if (!Array.isArray(fix) || fix.length !== 2) return null;
    const [kind, value] = fix;
    const ok = (kind === "verb" && ALLOWED_VERBS.has(value)) || (kind === "env" && ALLOWED_ENV.has(value)) ||
      (kind === "args" && ALLOWED_ARGS.has(value));
    if (!ok) return null;
    if (!clean.some(([k, v]) => k === kind && v === value)) clean.push([kind, value]);
  }
  clean.sort((a, b) => (a[0] + a[1]).localeCompare(b[0] + b[1]));
  return { machine, program, gpu, outcome, config: JSON.stringify({ line, profile, fixes: clean }) };
}

async function report(request, env) {
  const length = Number(request.headers.get("content-length") || 0);
  if (length > MAX_BODY) return json({ error: "too large" }, 413);
  let body;
  try {
    const text = await request.text();
    if (text.length > MAX_BODY) return json({ error: "too large" }, 413);
    body = JSON.parse(text);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  const items = Array.isArray(body) ? body : [body];
  if (items.length === 0 || items.length > MAX_BATCH) return json({ error: "bad batch" }, 400);
  const valid = items.map(validate);
  if (valid.some((v) => v === null)) return json({ error: "invalid report" }, 400);

  // Napi korlát címenként (a cím csak sózott hash-ként kerül az adatbázisba, és naponta új só)
  const day = new Date().toISOString().slice(0, 10);
  const ip = await sha256(`${env.SALT}|${day}|${request.headers.get("cf-connecting-ip") || ""}`);
  const row = await env.DB.prepare(
    "INSERT INTO rate (day, ip, count) VALUES (?1, ?2, ?3) " +
      "ON CONFLICT (day, ip) DO UPDATE SET count = count + ?3 RETURNING count",
  ).bind(day, ip, valid.length).first();
  if (row && row.count > DAILY_LIMIT) return json({ error: "rate limited" }, 429);

  const now = Date.now();
  const statements = [];
  for (const v of valid) {
    const machine = await sha256(`${env.SALT}|${v.machine}`);
    statements.push(env.DB.prepare(
      "INSERT INTO reports (machine, program, gpu, config, outcome, updated) " +
        "VALUES (?1, ?2, ?3, ?4, ?5, ?6) " +
        "ON CONFLICT (machine, program, gpu, config) DO UPDATE SET outcome = ?5, updated = ?6",
    ).bind(machine, v.program, v.gpu, v.config, v.outcome, now));
  }
  await env.DB.batch(statements);
  // A régi korlát-sorok takarítása (olcsó, a táblában csak néhány nap van)
  await env.DB.prepare("DELETE FROM rate WHERE day < ?1").bind(day).run();
  return json({ ok: true, accepted: valid.length });
}

async function exportKnowledge(request, env) {
  const auth = request.headers.get("authorization") || "";
  if (!env.EXPORT_TOKEN || auth !== `Bearer ${env.EXPORT_TOKEN}`) return json({ error: "unauthorized" }, 401);
  const { results } = await env.DB.prepare(
    "SELECT program, gpu, config, " +
      "SUM(outcome = 'worked') AS worked, SUM(outcome = 'failed') AS failed " +
      "FROM reports GROUP BY program, gpu, config",
  ).all();
  const programs = {};
  for (const r of results) {
    const total = r.worked + r.failed;
    if (r.worked < MIN_MACHINES || r.worked / total < MIN_SUCCESS) continue;
    const best = programs[r.program]?.[r.gpu];
    if (best && best.machines >= r.worked) continue;
    programs[r.program] ??= {};
    programs[r.program][r.gpu] = { ...JSON.parse(r.config), machines: r.worked };
  }
  return json({ version: 1, programs });
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (request.method === "POST" && pathname === "/v1/report") return report(request, env);
    if (request.method === "GET" && pathname === "/v1/export") return exportKnowledge(request, env);
    if (request.method === "GET" && pathname === "/") return json({ service: "Sloth OS knowledge" });
    return json({ error: "not found" }, 404);
  },
};
