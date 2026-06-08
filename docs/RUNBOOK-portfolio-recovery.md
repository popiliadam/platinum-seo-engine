# Portfolio Recovery Runbook

> Scope: **Faz-4 portfolio operations** — the cost/quota ledger (4a), the
> sequential portfolio sweep (4b), the read-only portfolio triage (4c), and the
> optional recurring scheduler (4d). This is a read-only reference document; it
> changes no engine behavior. Provenance: AMO design spec
> `docs/superpowers/specs/2026-06-05-agentic-orchestration-multiproject-design.md`
> (§7 Phase 4, §8) and the manager roadmap `docs/superpowers/plans/amo/MANAGER.md`
> (batch 4e).

Faz-4 lets the engine operate across the whole portfolio in one pass instead of
one project at a time. That pass runs under a hard global budget ceiling, so it
can deliberately **stop** (a kill-switch), **skip** a project that is already
running, or **fail** a single project without taking the rest down. It can also
be put on an optional recurring schedule. Each of those outcomes prints a Turkish
operator block with one next action; this runbook is the authoritative index of
*what you will see* for every outcome and *the exact copy-pasteable command* to
recover — written for an operator with no terminal and no Python. Every quoted
message below is copied verbatim from the shipped source.

> **Safety order before arming autonomy.** The scheduler (4d) is **default OFF**
> and the engine **fires nothing itself** — the periodic trigger is external (see
> §6). Arm autonomy only in this order:
>
> 1. **Set all three ceilings** (`gsc_calls`, `dfs_credits`, `image_spend`) in
>    `shared/cost-ceilings.json`. An unset ceiling means "no cap" for a manually
>    watched sweep, which is fine — but it is refused for an unattended schedule.
> 2. **Run the one comprehensive live acceptance once** (spec §8 / D11: autonomy
>    must not arm until the loop is demonstrated live in every target
>    environment).
> 3. **Only then** `/pseo-schedule arm <workflow> <cadence>` and wire the
>    external trigger (§6).

---

## 1. Reading the portfolio triage (`/pseo-status-portfolio`)

`/pseo-status-portfolio [period]` is the read-only, portfolio-wide companion to
the per-project `/pseo-status`. It writes nothing. It prints one Turkish block:
a project triage table, a "Yapılacaklar" (to-do) list of next actions for every
non-healthy project, and a global budget table. `period` defaults to today's UTC
date.

The **durum** (status) column has exactly five categories:

| Triage label (verbatim) | Category | neden (cause) | What it means | What to do |
|---|---|---|---|---|
| `✅ sağlıklı` | healthy | `—` | All required steps satisfied (verdict `pass`). | Nothing. |
| `📋 eksik` | owed | `iç` (internal) | A required step is missing (verdict `incomplete`). | Re-run the project: `/pseo-run <workflow> <slug>`. |
| `❌ başarısız` | failed | `iç` (internal) | An internal gate rejected a step (verdict `failed`). | Fix, then re-run: `/pseo-run <workflow> <slug>`. |
| `⏸️ duraklatıldı` | paused | `dış` (external) | An external dependency stalled it (budget exhausted, GSC/DFS outage). | Wait for the dependency to recover; it resumes. |
| `➖ kayıt yok` | none | `—` | The project has never run. | Start it: `/pseo-run <workflow> <slug>`. |

The "Yapılacaklar" list prints the generic next-action hint for each non-healthy
row verbatim, for example:

```
- <slug>: eksik adım(lar) var → `/pseo-run <workflow> {slug}` ile tamamla
- <slug>: iç geçit reddetti → düzelt + `/pseo-run <workflow> {slug}` ile yeniden çalıştır
- <slug>: dış bağımlılık/bütçe bekliyor → yenilenince kaldığı yerden devam eder
- <slug>: henüz çalıştırılmadı → `/pseo-run <workflow> {slug}` ile başlat
```

The **budget block** is one global summary per resource (not per project):

```
Bütçe (global, dönem: <period>):
| kaynak | kullanım | tavan | kalan |
|---|---|---|---|
| gsc_calls | <used> | <ceiling | sınırsız> | <remaining | —> |
| dfs_credits | … | … | … |
| image_spend | … | … | … |
```

- **`tavan` = `sınırsız`** means that resource's ceiling is **unset** in
  `shared/cost-ceilings.json` — there is no cap, so `kalan` (remaining) shows `—`.
  This is allowed for a manual sweep but blocks arming the scheduler (§6).
- **`kullanım` = `HATA`** on a row means the cost ledger chain is broken for that
  resource — see §5. Other resources and the project table still render.

If the portfolio is empty the block is replaced by:

```
Portföyde proje yok — `/pseo-init` ile bir proje başlat.
```

---

## 2. Budget kill-switch fired (a project `paused`, the rest `not_run`)

**What you will see.** After `/pseo-run-portfolio <workflow>`, the summary block
shows a non-zero `duraklatıldı (bütçe)` count and names the exhausted resource and
the resume command:

```
📊 Portföy taraması — workflow: <workflow> (<period>)
   ✅ çalıştırıldı: <n>
   ⏭️  atlandı (kilitli): <n>
   ⏸️  duraklatıldı (bütçe): <n>
   ❌ başarısız: <n>
   ⏳ çalıştırılmadı: <n>

⚠️  Bütçe tavanı aşıldı: <resource> (kill-switch) — duraklatılan proje: <slug>.
Bütçe yenilenince kaldığın yerden devam et:
/pseo-run-portfolio <workflow>
```

The paused project's own line reads:

```
⏸️  <slug>: bütçe tavanı aşıldı (<resource>: <current>+<requested> > <ceiling>). Portföy taraması durduruldu; bütçe yenilenince kaldığı yerden devam eder.
```

and every project after it is marked:

```
⏳ <slug>: portföy taraması bütçe tavanı nedeniyle durdu — çalıştırılmadı (bütçe yenilenince taranır).
```

**Why.** Before each project the sweep reserves that workflow's estimated cost
against the hard ceiling. When a reservation would push a resource over its
ceiling for this period, the engine fires the **kill-switch**: it releases the
partial reservations it already made for that project (no budget leak), marks the
project `paused`, marks every remaining project `not_run`, and **stops** the
sweep. It pauses rather than silently under-running.

**No data is lost.** The partial reservations were released and the append-only,
hash-chained ledger stays intact. The paused project simply did not run.

**Recover.**

1. Inspect the exhausted resource:

   ```
   python3 -m scripts.state.cost_ledger usage <resource> <period>
   ```

   It prints `usage:`, `ceiling:` (or `unset`), and `remaining:` (or `unset`).
   Use the same `<period>` the sweep used (today's UTC date, e.g. `2026-06-08`).

2. Make headroom, either:
   - **raise the ceiling** for that resource in `shared/cost-ceilings.json`
     (a plain operator-edited number), or
   - **wait for the period to reset** — a new UTC date is a fresh pool
     (daily-reset semantics; the ledger partitions usage by `period`).

3. Re-run the sweep with the exact command from the summary:

   ```
   /pseo-run-portfolio <workflow>
   ```

   The sweep walks the portfolio again from the top so the projects the
   kill-switch left `not_run` are processed. Per-project workflows are idempotent
   (whole-block replace), so a project that already completed is not duplicated.
   Because the ledger is append-only and per-period, make sure there is headroom
   first (step 2) — otherwise the kill-switch fires again at the same point.

---

## 3. A project was skipped (lock held)

**What you will see.** A non-zero `atlandı (kilitli)` count, with the project's
line:

```
⏭️  <slug>: zaten başka bir oturumda çalışıyor — atlandı (kilit serbest kalınca tekrar denenebilir).
```

**Why.** Each project runs under its own per-project advisory lock
(`shared/locks/<slug>.lock`). The lock is **non-blocking**: if the project is
already running in another bound session or another sweep, the sweep skips it and
moves on — it never waits (a sweep that blocked on one busy project would stall
the whole portfolio).

**Stale vs. live lock.** The advisory lock is held by a running process, not by
the file. A `.lock` file on disk does **not** mean the lock is held — the file is
created once and left in place; the operating system releases the *lock*
automatically the moment the holding process exits. So:

- If another session/sweep is genuinely running that project, **let it finish**,
  then re-run. That is the normal case and needs no intervention.
- If the project keeps being skipped but **no** other session or sweep is running,
  the previous holder already exited and the OS has already freed the lock — the
  next attempt will acquire it. Just re-run `/pseo-run-portfolio <workflow>`.

Do **not** delete a `.lock` file to "force" a run: if a process is still holding
it, the file is irrelevant (the lock is in the kernel), and deleting it does not
release anything. There is no situation where hand-deleting the lock file is the
correct recovery.

---

## 4. A single project failed mid-sweep

**What you will see.** A non-zero `başarısız` count (this is **not** a
kill-switch — the sweep kept going), with the project's line:

```
❌ <slug>: proje çalışması hata verdi (<error>); bütçe serbest bırakıldı, tarama sonraki projeyle devam etti.
```

In the triage table that project shows `❌ başarısız` with neden `iç` (internal).

**Why.** That one project's workflow errored, or its verdict was not `pass`. A
single project's failure is **not** a kill-switch: the sweep released that
project's reservations and **continued** to the next project. Only a budget
ceiling stops the whole sweep (§2).

**Recover.** Fix the cause if it is obvious, then re-run just that one project
with the per-project driver (it supports `--resume` to retry only the
missing/failed steps):

```
/pseo-run <workflow> <slug> --resume
```

Or re-sweep the whole portfolio with `/pseo-run-portfolio <workflow>`. The triage
"Yapılacaklar" list already prints the per-project hint for you.

---

## 5. Cost ledger chain broken

**What you will see.** A sweep, the triage, or the usage CLI surfaces a
"chain broken" error. In the triage budget table the resource row reads `HATA`
with the message; via the CLI you get:

```
error: cost ledger chain broken at entry <idx>; refusing to report usage
```

**What it means.** The cost ledger (`shared/cost_ledger.jsonl`) is an
**append-only, SHA-256 hash-chained** log: each line's hash binds the previous
line's hash, so a forged, rewritten, reordered, or hand-edited line breaks the
chain. When the chain does not verify, `usage()` fails **closed** — it refuses to
report rather than silently under-report, because an under-reported usage could
let a real budget be overspent. This is tamper detection, not a transient glitch.

**Inspect.** The error names the first broken entry index:

```
python3 -m scripts.state.cost_ledger usage <resource> <period>
```

The portfolio triage degrades gracefully — the affected resource shows `HATA`
while every other resource and the whole project table still render — so one
broken ledger never blanks the portfolio view.

**Recovery posture.**

- **Do not hand-edit the ledger** to "repair" a hash. Editing it defeats the
  tamper-evidence the chain exists to provide and will not restore trust in the
  numbers.
- A broken chain is **surfaced, never silently ignored** — treat it as an
  escalation. The honest fix is to restore `shared/cost_ledger.jsonl` from a
  known-good copy (the workspace's version control history), not to patch the
  log in place. The engine will not auto-repair a tampered ledger.

---

## 6. Scheduler: arm / disarm / status (`/pseo-schedule`)

`/pseo-schedule [status|arm|disarm] [workflow] [cadence]` is the only surface for
the optional recurring schedule. The schedule marker is global
(`shared/schedule.json`) and **default OFF** — an absent file is a disarmed
schedule. This command **fires nothing**; it only records intent (see the
external trigger below).

**status** (also shown first for every sub-command). Disarmed:

```
Zamanlanmış görev YOK (varsayılan KAPALI).
```

Armed:

```
Zamanlanmış görev AÇIK (armed):
  workflow : <workflow>
  cadence  : <cadence>
  armed_at : <iso>
  öngörülen GÜNLÜK maliyet: <resource: cost, …>
```

**arm** is gated three ways, in order:

1. **Valid `workflow` + `cadence`.** workflow ∈ `monthly | audit | setup |
   content`; cadence ∈ `daily | weekly | monthly`. An invalid value stops with a
   `GEÇERSIZ` message naming the valid set.
2. **O5 fail-closed ceiling gate.** If *any* of the three ceilings is unset, arm
   **refuses and writes nothing**. You will see the refusal explained in Turkish:
   an unattended schedule cannot be armed while a cost ceiling is unset; the
   resource(s) with no ceiling are named; the fix is to put a numeric ceiling for
   each resource in `shared/cost-ceilings.json` (for example
   `{"gsc_calls": 1000, "dfs_credits": 500, "image_spend": 50}`), then try again.
   The underlying guard raises:

   ```
   cannot arm an unattended schedule while a cost ceiling is unset (O5 fail-closed); unset: <names>. Set them in shared/cost-ceilings.json before arming.
   ```

3. **Explicit per-cadence consent.** After the gate passes, the command shows the
   projected cost — `project_count`, per-sweep cost, and projected **daily** cost
   per resource — and asks for an explicit confirmation before arming anything:

   ```
   Bu cadence (<cadence>) + öngörülen günlük maliyeti onaylıyor musun? Onaylarsan program armed olur (gözetimsiz). Devam? (evet / hayır)
   ```

   It never shows the cost and arms in the same turn. Only an explicit "evet"
   arms it. Changing the cadence or workflow later is a fresh arm with fresh
   consent, never a silent re-arm.

The armed marker records the `projected_daily_cost` the operator saw
(transparency).

**disarm** rewrites the marker `armed=false` (it never deletes it) and is
idempotent:

```
Zamanlanmış görev KAPATILDI (armed=false). Tekrar açmak için `/pseo-schedule arm <workflow> <cadence>`.
```

### The external trigger (plugin-agnostic)

An armed schedule is a **record of intent only** — the engine never fires it. The
actual periodic trigger is **external**: the operator's OS scheduler (`cron` /
`launchd`), or a Claude Code scheduled task / `/loop`, invokes
`/pseo-run-portfolio <workflow>` on the chosen cadence. The shape is simply
"run the portfolio command on a timer", for example a weekly cron line:

```
# 03:00 every Monday — run the portfolio monthly workflow
0 3 * * 1   <invoke Claude Code to run: /pseo-run-portfolio monthly>
```

The exact invocation depends on your environment (Mac app scheduled task,
headless CLI, or `/loop`); whatever the mechanism, it must call
`/pseo-run-portfolio <workflow>` on the cadence — there is no engine-internal
daemon. Each fired sweep is still bounded by the same 4a ledger ceiling and the
kill-switch (§2), so an external trigger can never overspend the cap you set.

**Reiterate D11:** arm and wire the external trigger **only after** the one
comprehensive live-acceptance run (spec §8). Follow the safety order at the top of
this document: ceilings first, live acceptance second, arm + external trigger
last.

---

## 7. Quick reference

| Symptom (what you see) | Command | One-line action |
|---|---|---|
| Triage shows `📋 eksik` / `❌ başarısız` / `➖ kayıt yok` | `/pseo-run <workflow> <slug>` | Re-run that project (use `--resume` to retry only failed steps). |
| Triage shows `⏸️ duraklatıldı` | — | External dependency/budget; it resumes when the dependency recovers. |
| Budget row `tavan` = `sınırsız` | edit `shared/cost-ceilings.json` | Set a numeric ceiling (required before arming the scheduler). |
| Sweep: `⏸️ duraklatıldı (bütçe)` + `kill-switch` | `python3 -m scripts.state.cost_ledger usage <resource> <period>` then `/pseo-run-portfolio <workflow>` | Inspect usage, raise the ceiling or wait for the period reset, then re-sweep. |
| Sweep: `⏭️ atlandı (kilitli)` | `/pseo-run-portfolio <workflow>` | Let the other run finish, then re-run; never delete the `.lock`. |
| Sweep: `❌ başarısız` (sweep continued) | `/pseo-run <workflow> <slug> --resume` | Re-run just that one project. |
| Budget row `HATA` / `chain broken at entry N` | `python3 -m scripts.state.cost_ledger usage <resource> <period>` | Tamper detected (fail-closed); restore `shared/cost_ledger.jsonl` from version control — do not hand-edit. |
| Want a recurring sweep | `/pseo-schedule arm <workflow> <cadence>` | Set all 3 ceilings + run live acceptance first, then arm + wire the external trigger. |
| Check / stop a recurring sweep | `/pseo-schedule status` · `/pseo-schedule disarm` | Status is read-only; disarm rewrites the marker `armed=false`. |

---

## How it works under the hood (provenance)

This document describes — and changes nothing about — these shipped surfaces:

- Cost/quota ledger (4a): `scripts/state/cost_ledger.py` + `schemas/cost-ledger.schema.json`
  + the global `shared/cost_ledger.jsonl`; operator configs `shared/cost-ceilings.json`
  (ceilings) and `shared/cost-estimates.json` (per-workflow estimates).
- Portfolio sweep (4b): `commands/pseo-run-portfolio.md` + `scripts/orchestration/portfolio_runner.py`
  + per-project lock `scripts/state/project_lock.py`.
- Portfolio triage (4c): `commands/pseo-status-portfolio.md` + `scripts/reporting/portfolio_status.py`.
- Scheduler (4d): `commands/pseo-schedule.md` + `scripts/state/schedule.py`
  + `schemas/schedule.schema.json` + the global `shared/schedule.json`.
- Per-project driver reused for recovery: `commands/pseo-run.md`.
