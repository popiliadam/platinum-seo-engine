---
description: |
  Use when: kullanıcı "durum", "status", "ne yapıyoruz", "aktif workflow", "neredeyiz", "mevcut run'lar" der ya da `/pseo-status` çağırırsa.
  Also use when: bir oturumun başında aktif projenin _state/workflows/ altında bekleyen `running`, `paused`, `awaiting_approval` run'larını listelemek; sonraki adım için Phase 5 `whats-next` skill'ine routing önermek gerekir.
  Do not use when: yeni proje açma (`/pseo-init`), aylık rapor (`/pseo-monthly`), drift kontrol (`/pseo-driftcheck`) veya quick-win analizi (`/pseo-quickwin`) istendiğinde — her birinin kendi komutu vardır.
argument-hint: "[project-slug]"
allowed-tools: Bash(python3:*), Bash(cat:*), Bash(jq:*), Bash(ls:*), Read
model: sonnet
---

# /pseo-status — Aktif Workspace Durumu

Aktif projenin workflow run state'ini ve önerilecek sonraki adımı listele.

## 1. Aktif proje slug'ını çöz

`$1` verilmişse onu kullan; yoksa `shared/active.json`'dan oku.

Aktif marker: !`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT"; else echo "active=$PROJECT"; fi; fi`

Eğer çıktı `NO_ACTIVE_PROJECT` ise: kullanıcıdan slug iste veya `/pseo-active <slug>` çağırmasını öner; aşağıdaki adımları atla.

## 2. workflow_runner.list_runs() çağrısı

`scripts/state/workflow_runner.py` modül CLI olarak değil, Python `import` ile expose edilmiş (bkz. `list_runs(project_slug, *, workspace_root=None, status_filter=None)` — döndürdüğü liste `RunHandle` dataclass'lardır). Inline Python ile çağır:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş — kullanıcıya workspace path'ini sor"; exit 2; fi; PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ['CLAUDE_PLUGIN_ROOT'])
from scripts.state import workflow_runner as wr
ws_path = Path(os.environ['PSEO_WORKSPACE_ROOT']).expanduser()
slug = '$PROJECT'
if not slug:
    print('NO_ACTIVE_PROJECT', file=sys.stderr); sys.exit(2)
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
