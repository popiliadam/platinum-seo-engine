# Glossary

Bu sözlük spec içi terminolojinin canlı kataloğudur. Her teknik terim burada tanımlı olmalı (Disiplin #8 — Glossary Discipline). Eksik bulunan terim için `glossary-audit` skill'i AMBER warn üretir. Alfabetiktir; spec §20'deki çekirdek terimler + Phase 0 bootstrap kararlarından eklenenler.

---

- **ADR** — Architecture Decision Record. `docs/DECISIONS.md`'de append-only kayıtlı bir mimari karar entry'si.
- **Command** — Slash (`/pseo-*`) ile tetiklenen kısayol; markdown dosyasında tanımlı.
- **Drift** — Schema, glossary, catalog ve gerçek state arasındaki tutarsızlık. `drift-check` skill'i ile denetlenir.
- **Gateway Phase** — Bir sonraki phase'lere geçişin koşullu olduğu phase (ör. Phase 5 GO/NO-GO). Acceptance kriteri geçmezse roadmap ilerlemez.
- **Hook** — Olay tetikli script (session-start, pre/post-tool-use, user-prompt-submit). Plugin'in claude code lifecycle'ına bağlandığı yer.
- **Hybrid mode** — v1.8 SF integration strategy: file-based sf-import remains authoritative + SF MCP adds operator-triggered crawl + ad-hoc query capability. File-drop fallback never deprecated (D-SF-07).
- **Invariant** — Cross-sheet rule, master.xlsx içi sheet'ler arası kural. 31 CSR rule mevcut (`schemas/cross-sheet-invariants.json` `rules` SoT; v1.8 SF MCP invariant'ları dahil); her Excel write sonrası denetlenir.
- **Manager Session** — Karar verici Claude session'ı. Kod yazmaz; plan yapar, worker yönlendirir, ADR yazar.
- **Optional consumer** — A discovery/planning skill with `use_sf_mcp_live: bool` flag (default False); when True, calls SF MCP for live data instead of file-based fixtures. v1.8 Phase 5 wires tech-audit + schema-audit + on-page-audit + internal-links opt-in.
- **Phase** — Roadmap'teki tek bir adım; kendi acceptance kriteri olan iş paketi.
- **Pilot Project** — v1 acceptance test'inde kullanılan proje, **demo-dental** (ADR-003). Eski `~/Documents/platinum-premium-seo/` repo'sunda en olgun klasör.
- **Plugin** — `platinum-seo-engine` repo'su. Logic, skill, command, hook, schema barındıran proje-agnostik kısım.
- **Repo Hierarchy** — Plugin (logic) + Workspace (data/state) ayrımı. İki repo arası sözleşme spec §2.3'te.
- **Schema** — JSON Schema dosyası (`schemas/*.schema.json`); data shape kontratı. Schema-First disiplini gereği veri yazılmadan ÖNCE var olmalı.
- **SF MCP** — Native Screaming Frog 24 Model Context Protocol server (HTTP `http://127.0.0.1:11435/mcp`). v1.8'de 4'üncü MCP server olarak `.mcp.json`'a eklendi (ADR-039). İlk HTTP transport MCP'si; stdio kullanan diğer 3'ten ayrılır.
- **SF orchestrator** — `skills/ingestion/sf-crawl-orchestrator/SKILL.md` — SF MCP'yi file-based sf-import pipeline'ına bridge'leyen skill. 24-report iteration + atomic semantics (D-SF-16) + resume capability + 8 DURUR.
- **Skill** — Doğal dil ile tetiklenen yetenek. Markdown dosyasında frontmatter + body olarak tanımlı.
- **Soak Period** — v1 acceptance sonrası eski repo'lar (`platinum-seo-core`, `platinum-premium-seo`) silinmeden önceki **1 haftalık** bug surface süresi (ADR-004). Bu süre boyunca eski dosyalar READ-ONLY referans.
- **Worker Session** — Manager tarafından dispatch edilen, dar scope'lu Claude session'ı. Manager'ın belirlediği görevi tek başına yapar.
- **Workflow** — Multi-step bir skill'in çalışma süreci. State `workflow-run.schema.json`'a uygun JSON ile tutulur (resume/retry/approval gate destekli).
- **Workspace** — `platinum-seo-workspace` repo'su. Proje verisi, state, output, raw data tutar; logic içermez.
