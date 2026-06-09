---
description: |
  Use when: kullanıcı "durum", "status", "ne yapıyoruz", "aktif workflow", "neredeyiz", "mevcut run'lar" der ya da `/pseo-status` çağırırsa.
  Also use when: bir oturumun başında aktif projenin _state/workflows/ altında bekleyen `running`, `paused`, `awaiting_approval` run'larını listelemek; sonraki adım için Phase 5 `whats-next` skill'ine routing önermek gerekir.
  Do not use when: yeni proje açma (`/pseo-init`), aylık rapor (`/pseo-monthly`), drift kontrol (`/pseo-driftcheck`) veya quick-win analizi (`/pseo-quickwin`) istendiğinde — her birinin kendi komutu vardır.
argument-hint: "[project-slug]"
allowed-tools: Bash(python3:*), Bash(cat:*), Bash(jq:*), Bash(ls:*), Bash(curl:*), Bash(find:*), Bash(grep:*), Bash(sort:*), Bash(tail:*), Bash(xargs:*), Read
model: sonnet
---

# /pseo-status — Aktif Workspace Durumu

Aktif projenin workflow run state'ini ve önerilecek sonraki adımı listele.

## 1. Aktif proje slug'ını çöz

`$1` verilmişse onu kullan; yoksa `shared/active.json`'dan oku.

Aktif marker: !`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT"; else echo "active=$PROJECT"; fi; fi`

**Engine path resolution** — `CLAUDE_PLUGIN_ROOT` Claude Code tarafından set edilmediyse fallback gerekli. Command altyapısı: `${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-$(find /Users/apple/.claude/plugins/cache/*/platinum-seo-engine* -type d 2>/dev/null | sort -V | tail -1)}}` formatı denenir.

Eğer çıktı `NO_ACTIVE_PROJECT` ise: kullanıcıdan slug iste veya `/pseo-active <slug>` çağırmasını öner; aşağıdaki adımları atla.

## 2. workflow_runner.list_runs() çağrısı

`scripts/state/workflow_runner.py` modül CLI olarak değil, Python `import` ile expose edilmiş (bkz. `list_runs(project_slug, *, workspace_root=None, status_filter=None)` — döndürdüğü liste `RunHandle` dataclass'lardır). Inline Python ile çağır:

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş — kullanıcıya workspace path'ini sor"; exit 2; fi; ENGINE_ROOT="${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-$(find /Users/apple/.claude/plugins/cache 2>/dev/null -type d -name 'platinum-seo-engine' | sort | tail -1 | xargs -I{} find {} -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort -V | tail -1)}}"; if [ -z "$ENGINE_ROOT" ]; then echo "ERROR: CLAUDE_PLUGIN_ROOT yok ve fallback bulunamadı — PSEO_ENGINE_ROOT env var set edin"; exit 3; fi; PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; PSEO_ENGINE_ROOT="$ENGINE_ROOT" PYTHONPATH="$ENGINE_ROOT" PROJECT="$PROJECT" python3 -c "
import json, os, re, sys
from pathlib import Path
engine = os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('PSEO_ENGINE_ROOT')
if not engine:
    print('ERROR: engine path resolution failed', file=sys.stderr); sys.exit(3)
sys.path.insert(0, engine)
from scripts.state import workflow_runner as wr
ws_path = Path(os.environ['PSEO_WORKSPACE_ROOT']).expanduser()
slug = os.environ.get('PROJECT', '')
if not slug:
    print('NO_ACTIVE_PROJECT', file=sys.stderr); sys.exit(2)
if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', slug):
    print('ERROR: invalid project slug (lowercase alnum + hyphen only): ' + repr(slug), file=sys.stderr); sys.exit(2)
try:
    runs = wr.list_runs(slug, workspace_root=ws_path)
except wr.WorkflowError as e:
    print(f'workflow_runner error: {e}', file=sys.stderr); sys.exit(1)
out = [{'run_id': r.run_id, 'skill': r.data.get('skill'), 'status': r.status,
        'current_step': r.data.get('current_step'), 'total_steps': r.data.get('total_steps'),
        'updated_at': r.data.get('updated_at')} for r in runs]
print(json.dumps({'project': slug, 'count': len(out), 'runs': out}, indent=2, ensure_ascii=False))
" 2>&1`

## 3. Listeyi yorumla

Çıktıyı oku ve aşağıdaki tabloya çevir:

| run_id | skill | status | step | son güncelleme |
|---|---|---|---|---|

Status grupları:
- `running`: aktif olarak çalışan; resume gerekmez.
- `awaiting_approval`: onay bekliyor; kullanıcıya sun, `approve` veya `reject` öner.
- `paused`: duraklatılmış; `resume` çağrısı önerilebilir.
- `failed`: hatalı sonlanmış; `retry` veya inceleme öner.
- `done`: tamamlanmış; arşiv adayı.

Hiç run yoksa: `whats-next` skill'inin önereceği başlangıç noktasını sun (Phase 5'te `skills/meta/whats-next` yazılana kadar manuel öneri: SF crawl mı, GSC pull mı, quick-win mı).

## 4. Sonraki adım önerisi (whats-next skill chain)

Hiç run yoksa veya kullanıcı "şimdi ne yapayım" sorduğunda `skills/meta/whats-next/SKILL.md` (Phase 5, aktif) `scripts/meta/whats_next.py` üzerinden T-9NNNN router band ile Top-3 ranking üretir. Bu komut listeyi sunduktan sonra whats-next çıktısını yorumlamak için doğrudan skill'i çağırabilir.

## 5. SF MCP Status

> **v1.8 NEW** — Screaming Frog 24 MCP server bağlantı durumu + son sf-crawl-orchestrator run özeti.

SF MCP server health probe (v1.8 ADR-039: HTTP transport `http://127.0.0.1:11435/mcp`):

!`curl -sf -m 3 -X POST http://127.0.0.1:11435/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"sf_list_allowed_base_directory","arguments":{}}}' 2>/dev/null | jq -r '.result.content[0].text // "DOWN — SF GUI MCP Server kapalı veya port 11435 unreachable"' || echo "DOWN — SF GUI MCP Server kapalı veya port 11435 unreachable"`

Aktif projenin son SF crawl özeti (`_state/workflows/*.json` filter by skill=sf-crawl-orchestrator):

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "skip: PSEO_WORKSPACE_ROOT set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; WF_DIR="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/workflows"; if [ -d "$WF_DIR" ]; then grep -l '"skill": "sf-crawl-orchestrator"' "$WF_DIR"/*.json 2>/dev/null | xargs -I{} jq -r '[.run_id, .status, (.updated_at // "n/a")] | @tsv' {} 2>/dev/null | sort -k3 | tail -1 || echo "NO_SF_CRAWL"; else echo "skip: workflow dizini yok"; fi; fi`

Detaylı SF MCP status tablosu için: `/pseo-sf-status [<slug>]` (4-kolonlu: project_slug, last_crawl_date, sf_mcp_connection_status, allowed_directory_path).
