# Installation

> Status: **alpha (v0.1.0)** — Phase 0 active. Plugin fonksiyonel değil; kurulum talimatları placeholder.

## Requirements

- Claude Code CLI (en güncel sürüm önerilir; minimum sürüm TBD)
- Python 3.10+ (script'ler için; exact minimum spec'te belirtilmemiş — TBD Phase 3)
- Node 18+ (claude code runtime için TBD; spec exact pin koymuyor)

## Plugin Install

```bash
git clone <repo-url> ~/Documents/platinum-seo-engine
claude /plugin add ~/Documents/platinum-seo-engine
```

> Not: GitHub repo henüz açılmadı (ADR-002). Phase 0 sonu local `git init` + initial commit yapılır; user repo'yu manuel açar. Gerçek `claude /plugin add` komut sözdizimi kullanılan Claude Code sürümüne göre değişebilir — install komutu test edilince doğrulanacak (open question).

## Workspace Setup

Workspace repo (`platinum-seo-workspace`) **Phase 14**'te yaratılır (ADR-005). O zamana kadar:

- `~/Documents/platinum-premium-seo/` mevcut workspace olarak **READ-ONLY** kullanılır.
- Path detection bu dizini gösterir.

Phase 14 sonrası: yeni workspace path'ine taşınır.

## Configuration

`.env` dosyası gerekli (template `.env.example` — Phase 4 deliverable):

```
PSE_WORKSPACE_PATH=~/Documents/platinum-premium-seo
# MCP credentials (Phase 5+ requirement):
# GSC_*=...
# DATAFORSEO_*=...
```

Secrets disiplini için `docs/CONTRIBUTING.md` ve `rules/secrets-management.md`.

## Verify

```
/pseo-status
```

> `/pseo-status` Phase 4 deliverable. Phase 0/1/2/3'te henüz çalışmaz.

## Status

- v0.1.0 alpha — Phase 0 (Manager Bootstrap) active
- Foundation tamamlanması beklenen: Phase 4
- v1 (~43 skill) hedefi: Phase 14
