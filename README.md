# Platinum SEO Engine

[![CI](https://github.com/popiliadam/platinum-seo-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/popiliadam/platinum-seo-engine/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/popiliadam/platinum-seo-engine?label=release)](https://github.com/popiliadam/platinum-seo-engine/releases/tag/v1.0.0)

Bir Claude Code plugin'i; SEO operasyonunu schema-locked workflow'larla yöneten motor.

**Status:** v1.0.0 — Phase 14 complete (2026-05-05) — [Release Notes](docs/RELEASE_NOTES_v1.0.0.md)

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

v1 hedefi: ~43 skill, 9 batch phase'e yayılmış (Phase 5–13). Foundation Phase 0–4'te kurulur. Pilot proje **dentnotion** (ADR-003).

## License

MIT (see `LICENSE`).

## Contact / Repo

- GitHub repo: https://github.com/popiliadam/platinum-seo-engine (PRIVATE)
- Workspace repo: https://github.com/popiliadam/platinum-seo-workspace (PRIVATE)
