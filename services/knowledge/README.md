# Sloth OS knowledge service

Shared, anonymous knowledge about which settings make Windows programs start on Sloth OS.

When the Sloth OS `.exe` handler (`files/system/usr/lib/sloth-os/sloth-exe/`) gets a program running —
possibly after its self-healing runner tried several settings — and the user has turned on
**Sloth Center → Windows programs → Share experiences** (off by default), the machine reports *which*
setting worked. Once a setting has worked on enough different machines, every Sloth OS machine uses it
as the first attempt for that program, so it starts on the first try.

## Architecture

```
Sloth OS machines ──POST /v1/report──▶ Cloudflare Worker + D1 (this folder)
                                              │  GET /v1/export (token), hourly
                                              ▼
                        GitHub Action in Sloth-OS-Linux/sloth-os-knowledge
                                              │  commits knowledge.json
                                              ▼
Sloth OS machines ◀──raw.githubusercontent.com── knowledge.json
```

- **Writing** goes to the Worker. Machines queue reports locally; `sloth-windows-prepare` sends them in
  the background, so launching a program never waits for the network.
- **Reading** is a static file on GitHub (`sloth-windows-prepare` downloads it). Downloading it reveals
  nothing about the machine, and the knowledge stays available even if the Worker is down.

## Privacy

A report contains only:

| Field     | Content |
|-----------|---------|
| `machine` | a random UUID generated on the machine (stored only as a salted hash) |
| `program` | SHA-256 of the program's normalized product name and `.exe` file name, computed on the machine. The service never sees the name |
| `gpu`     | `amd`, `nvidia`, `intel` or `other` |
| `line`, `profile`, `fixes` | the setting (see below) |
| `outcome` | `worked` or `failed` |

IP addresses are used only for rate limiting, as a salted hash with a daily-changing salt, and rows
older than a day are deleted. Turning sharing off deletes the local queue.

## Abuse protection

- **Allowlist only.** A report may only contain known values: Proton line (`UMU-Proton`, `GE-Proton`),
  profile (`default`, `nofsync`, `wined3d`), and fixes from a fixed list: winetricks components such as
  `vcrun2022`, Proton on/off switches such as `PROTON_USE_WINED3D` or `PROTON_ENABLE_NVAPI` (always set
  to `1`), and `--disable-gpu`. Arbitrary commands, environment variables, values or arguments cannot be
  spread. Machines apply the same allowlist again when reading.
- **ProtonDB seed.** The public knowledge file also contains settings derived from the ProtonDB data dump
  (see the `Sloth-OS-Linux/sloth-os-knowledge` repository), limited to the same allowlist.
- **One machine, one vote** per program, GPU and setting (the latest outcome counts).
- **Thresholds.** A setting is published only if it worked on at least 3 different machines and at least
  75% of the reports for it are successful.
- **Rate limit:** 500 reports per IP address per day; batches of at most 50; any invalid item rejects
  the whole batch.

Keep the allowlists in `src/worker.js` in sync with `sloth_exe/heal.py`, `sloth_exe/diagnose.py` and
`sloth_exe/community.py`.

## API

- `POST /v1/report` — JSON object or array (max. 50) of reports. `200 {"ok": true}`, `400` invalid,
  `413` too large, `429` rate limited.
- `GET /v1/export` — requires `Authorization: Bearer <EXPORT_TOKEN>`. Returns
  `{"version": 1, "programs": {"<program>": {"<gpu>": {"line", "profile", "fixes", "machines"}}}}`.
- `POST /v1/feedback` — feedback from Sloth Center (`sloth_center/feedback.py`):
  `{"kind": "bug"|"idea"|"other", "text": "10–5000 chars", "version", "lang", "log"?}`. Opens a GitHub issue in
  `FEEDBACK_REPO` with the labels `feedback` and the kind; the user's text goes into a code block (no mentions or
  links). The optional log (max. 512 KB) is **not** put in the issue: it is stored in `feedback_logs`, linked from
  the issue, readable only with `Authorization: Bearer <LOG_TOKEN>`, and deleted after 30 days. Max. 5 per
  address per day. `200 {"ok": true, "number": 42}`, `400` invalid, `429` rate limited, `502` GitHub error,
  `503` not configured.
- `GET /v1/feedback/log/<id>` — requires `Authorization: Bearer <LOG_TOKEN>`; returns the log as plain text.

## Deployment

Requires a (free) Cloudflare account and the `wrangler` CLI.

```sh
wrangler login
wrangler d1 create sloth-os-knowledge        # put the printed database_id into wrangler.toml
wrangler d1 execute sloth-os-knowledge --remote --file schema.sql
wrangler secret put SALT                     # long random string
wrangler secret put EXPORT_TOKEN             # long random string, also set in the knowledge repo
wrangler secret put GITHUB_TOKEN             # fine-grained token: Issues read/write on the feedback repo only
wrangler secret put LOG_TOKEN                # long random string, for reading attached logs
wrangler deploy
```

`FEEDBACK_REPO` (e.g. `Sloth-OS-Linux/feedback`) is a plain variable: `[vars]` in `wrangler.toml`.

Then set the Worker URL in `sloth_exe/community.py` (`REPORT_URL`), and in the
`Sloth-OS-Linux/sloth-os-knowledge` repository add the secrets `EXPORT_URL`
(`https://<worker>/v1/export`) and `EXPORT_TOKEN`.

Local testing: create `.dev.vars` with `SALT=…` and `EXPORT_TOKEN=…`, then
`wrangler d1 execute sloth-os-knowledge --local --file schema.sql` and `wrangler dev --local`.
