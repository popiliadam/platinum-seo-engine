# Platinum SEO Engine

[![CI](https://github.com/popiliadam/platinum-seo-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/popiliadam/platinum-seo-engine/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/popiliadam/platinum-seo-engine?label=release)](https://github.com/popiliadam/platinum-seo-engine/releases/latest)

Bir Claude Code plugin'i; SEO operasyonunu schema-locked workflow'larla yöneten motor.

**Status:** v1.5.0 — audit-closure milestone: Phase-1 (K-01+Y-01 url_normalize 10-file dedup) + Phase-2 (K-02 schema sync 20→27 + D-01 missing test coverage + O-04 CI Python sync + O-05 memory reconcile) + Phase-3 (Y-05 version_bump.py 5-file sync automation + Y-07 dump_workspace.py manager session summary + D-02/D-03 orphan archival) — 10 finding RESOLVED + 4 yeni script + 95 yeni test (970→1065 PASS, regression sıfır) — drift-check AMBER (F-16 + F-17 PASS, F-13 historical kalıntı) (2026-05-07) — [Release Notes](docs/RELEASE_NOTES_v1.5.0.md)

---

## Quick Start

```bash
# 1. Install plugin
git clone https://github.com/popiliadam/platinum-seo-engine ~/Documents/platinum-seo-engine
claude /plugin add ~/Documents/platinum-seo-engine

# 2. Configure credentials
cp ~/Documents/platinum-seo-engine/.env.example ~/Documents/platinum-seo-engine/.env
# edit .env: GOOGLE_APPLICATION_CREDENTIALS + DATAFORSEO_USERNAME/PASSWORD + PSEO_WORKSPACE_ROOT

# 3. Initialize a project (prompts for domain + brand)
/pseo-init

# 4. Run first analysis
/pseo-quickwin
```

Full setup: [docs/INSTALL.md](docs/INSTALL.md)

---

## Overview

`platinum-seo-engine` SEO operasyonunu VS Code + Claude Code üzerinden yöneten bir plugin sistemidir. Skills/commands/hooks ile orkestre edilen, JSON schema'larla kilitli, markdown ile insan-okunur, Excel + JSONL ile state tutan, her workflow'u resume/retry/approval gate'leriyle yöneten, drift-check ile kendini denetleyen, **proje-agnostik** bir SEO motoru.

Mevcut `platinum-seo-core` (Python paketi + MCP server) ve `platinum-premium-seo` (4. tasarım iterasyonu) drift, duplikasyon ve ucu açıklık üretiyordu. Sebep mimaride fazla kod, fazla katman, fazla otorite. Çözüm: **az kod + sıkı kural + tek otorite + makine-okunur sözleşmeler**. Plugin (logic) ile workspace (data/state) net ayrılır; her ikisi ayrı repo'da yaşar.

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — vision, two-repo strategy, 10 disciplines, phase roadmap, v1 acceptance criteria
- [Install](docs/INSTALL.md) — requirements + plugin install + configuration
- [Contributing](docs/CONTRIBUTING.md) — manager/worker protokolü, skill yazımı, phase discipline
- [Workflows](docs/WORKFLOWS.md) — v1 ~43 skill kataloğu (planned)
- [Glossary](docs/GLOSSARY.md) — spec terminolojisi
- [Decisions](docs/DECISIONS.md) — ADR'ler (append-only)

## Roadmap

- [Phase Status](docs/PHASE_STATUS.md) — current phase + history
- [Open Questions](docs/OPEN_QUESTIONS.md) — açık sorular ve bekleyen kararlar

v1 hedefi: ~43 skill, 9 batch phase'e yayılmış (Phase 5–13). Foundation Phase 0–4'te kurulur. Pilot proje **demo-dental** (ADR-003).

## License

MIT (see `LICENSE`).

## Contact / Repo

- GitHub repo: https://github.com/popiliadam/platinum-seo-engine (PRIVATE)
- Workspace repo: https://github.com/popiliadam/platinum-seo-workspace (PRIVATE)
