// Sloth OS shared knowledge: machines report anonymously which setting a Windows program started with,
// and what worked on many machines goes into the summary (the machines read it from GitHub, see README.md).
//
//   POST /v1/report   reports (at most 50 at a time), with strict validation
//   GET  /v1/export   the summary (only with EXPORT_TOKEN; called by the GitHub Action)
//   POST /v1/feedback Sloth Center's feedback: a GitHub issue (FEEDBACK_REPO, GITHUB_TOKEN); the log does not
//                     go into the issue but stays here, readable only with LOG_TOKEN (GET /v1/feedback/log/<id>)
//
// Only allowed settings can get in (see ALLOWED_*): no arbitrary command, environment variable
// or parameter can be spread through a report. The lists match the values in sloth_exe/heal.py, diagnose.py and
// community.py; if they grow there, they must grow here too (and in the knowledge repository's seed/protondb.py).

const ALLOWED_LINES = new Set(["UMU-Proton", "GE-Proton"]);
const ALLOWED_PROFILES = new Set(["default", "nofsync", "wined3d"]);
const ALLOWED_GPUS = new Set(["amd", "nvidia", "intel", "other"]);
const ALLOWED_VERBS = new Set([
  "d3dcompiler_42", "d3dcompiler_43", "d3dcompiler_46", "d3dcompiler_47", "d3dx10", "d3dx11_42", "d3dx11_43",
  "d3dx9", "dotnet48", "gdiplus", "mf", "mfc42", "msxml3", "msxml4", "msxml6", "physx", "riched20", "vb6run",
  "vcrun2005", "vcrun2008", "vcrun2010", "vcrun2012", "vcrun2013", "vcrun2022", "xact", "xinput",
]);
// Proton on/off switches (with the value "=1" on the machine); the same as ALLOWED_ENV in sloth_exe/community.py
const ALLOWED_ENV = new Set([
  "PROTON_USE_WINED3D", "PROTON_ENABLE_NVAPI", "PROTON_HIDE_NVIDIA_GPU", "PROTON_FORCE_LARGE_ADDRESS_AWARE",
  "PROTON_HEAP_DELAY_FREE", "PROTON_NO_D3D11", "PROTON_NO_D3D10", "PROTON_OLD_GL_STRING", "PROTON_NO_WRITE_WATCH",
]);
const ALLOWED_ARGS = new Set(["--disable-gpu"]);

const MAX_BATCH = 50;
const MAX_BODY = 64 * 1024;
const DAILY_LIMIT = 500;      // reports / address / day
const MIN_MACHINES = 3;       // it must work on this many different machines
const MIN_SUCCESS = 0.75;     // and at least this share of the reports must be successful

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

// Validates a report and returns its canonical form; null if anything is wrong
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

  // Daily limit per address (the address only goes into the database as a salted hash, with a new salt every day)
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
  // Cleaning up the old limit rows (cheap, the table only holds a few days)
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

// --- Feedback --------------------------------------------------------------------------------------

const FEEDBACK_KINDS = { bug: "Bug", idea: "Idea", other: "Other" };
const FEEDBACK_DAILY_LIMIT = 5;          // feedback / address / day
const FEEDBACK_MAX_TEXT = 5000;
const FEEDBACK_MAX_LOG = 512 * 1024;     // the log is at most this big (the machine sends its end)
const FEEDBACK_LOG_DAYS = 30;            // the log is deleted after this many days
const SHORT = /^[\p{L}\p{N} ._()+:,\/-]{0,120}$/u;

function fence(text) {
  // the user's text goes into a code block: no @mention, markdown or link works
  return "```text\n" + text.replaceAll("```", "ʼʼʼ") + "\n```";
}

async function feedback(request, env) {
  if (!env.GITHUB_TOKEN || !env.FEEDBACK_REPO) return json({ error: "not configured" }, 503);
  const length = Number(request.headers.get("content-length") || 0);
  if (length > FEEDBACK_MAX_LOG + 64 * 1024) return json({ error: "too large" }, 413);
  let body;
  try {
    body = JSON.parse(await request.text());
  } catch {
    return json({ error: "bad json" }, 400);
  }
  const { kind, text, version = "", lang = "", log = "" } = body || {};
  if (!(kind in FEEDBACK_KINDS)) return json({ error: "bad kind" }, 400);
  if (typeof text !== "string" || text.trim().length < 10 || text.length > FEEDBACK_MAX_TEXT) {
    return json({ error: "bad text" }, 400);
  }
  if (typeof version !== "string" || !SHORT.test(version) || typeof lang !== "string" || !SHORT.test(lang)) {
    return json({ error: "bad meta" }, 400);
  }
  if (typeof log !== "string" || log.length > FEEDBACK_MAX_LOG) return json({ error: "bad log" }, 400);

  const day = new Date().toISOString().slice(0, 10);
  const ip = await sha256(`${env.SALT}|feedback|${day}|${request.headers.get("cf-connecting-ip") || ""}`);
  const row = await env.DB.prepare(
    "INSERT INTO rate (day, ip, count) VALUES (?1, ?2, 1) " +
      "ON CONFLICT (day, ip) DO UPDATE SET count = count + 1 RETURNING count",
  ).bind(day, ip).first();
  if (row && row.count > FEEDBACK_DAILY_LIMIT) return json({ error: "rate limited" }, 429);

  let logLine = "Log: not attached";
  if (log) {
    const id = crypto.randomUUID();
    await env.DB.prepare("INSERT INTO feedback_logs (id, created, log) VALUES (?1, ?2, ?3)")
      .bind(id, Date.now(), log).run();
    const origin = new URL(request.url).origin;
    logLine = `Log (only with LOG_TOKEN, for ${FEEDBACK_LOG_DAYS} days): ${origin}/v1/feedback/log/${id}`;
  }
  const first = text.trim().split("\n")[0].slice(0, 70);
  const issue = {
    title: `[${FEEDBACK_KINDS[kind]}] ${first}`,
    body: [fence(text.trim()), "", `Version: \`${version || "?"}\` · Language: \`${lang || "?"}\``, logLine,
      "", "_Sent from the Sloth Center feedback page._"].join("\n"),
    labels: ["feedback", kind],
  };
  const gh = await fetch(`https://api.github.com/repos/${env.FEEDBACK_REPO}/issues`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      accept: "application/vnd.github+json",
      "user-agent": "sloth-os-feedback",
    },
    body: JSON.stringify(issue),
  });
  if (!gh.ok) return json({ error: "github", status: gh.status }, 502);
  const created = await gh.json();
  // cleaning up the old logs
  await env.DB.prepare("DELETE FROM feedback_logs WHERE created < ?1")
    .bind(Date.now() - FEEDBACK_LOG_DAYS * 86400 * 1000).run();
  return json({ ok: true, number: created.number });
}

async function feedbackLog(request, env, id) {
  const auth = request.headers.get("authorization") || "";
  if (!env.LOG_TOKEN || auth !== `Bearer ${env.LOG_TOKEN}`) return json({ error: "unauthorized" }, 401);
  const row = await env.DB.prepare("SELECT log FROM feedback_logs WHERE id = ?1").bind(id).first();
  if (!row) return json({ error: "not found" }, 404);
  return new Response(row.log, { headers: { "content-type": "text/plain; charset=utf-8" } });
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (request.method === "POST" && pathname === "/v1/report") return report(request, env);
    if (request.method === "GET" && pathname === "/v1/export") return exportKnowledge(request, env);
    if (request.method === "POST" && pathname === "/v1/feedback") return feedback(request, env);
    const logMatch = pathname.match(/^\/v1\/feedback\/log\/([0-9a-f-]{36})$/);
    if (request.method === "GET" && logMatch) return feedbackLog(request, env, logMatch[1]);
    if (request.method === "GET" && pathname === "/") return json({ service: "Sloth OS knowledge" });
    return json({ error: "not found" }, 404);
  },
};
