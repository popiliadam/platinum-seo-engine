# Glossary

Bu sözlük spec içi terminolojinin canlı kataloğudur. Her teknik terim burada tanımlı olmalı (Disiplin #8 — Glossary Discipline). Eksik bulunan terim için `glossary-audit` skill'i AMBER warn üretir. Alfabetiktir; spec §20'deki çekirdek terimler + Phase 0 bootstrap kararlarından eklenenler.

---

- **ADR** — Architecture Decision Record. `docs/DECISIONS.md`'de append-only kayıtlı bir mimari karar entry'si.
- **Command** — Slash (`/pseo-*`) ile tetiklenen kısayol; markdown dosyasında tanımlı.
- **Drift** — Schema, glossary, catalog ve gerçek state arasındaki tutarsızlık. `drift-check` skill'i ile denetlenir.
- **Gateway Phase** — Bir sonraki phase'lere geçişin koşullu olduğu phase (ör. Phase 5 GO/NO-GO). Acceptance kriteri geçmezse roadmap ilerlemez.
- **Hook** — Olay tetikli script (session-start, pre/post-tool-use, user-prompt-submit). Plugin'in claude code lifecycle'ına bağlandığı yer.
- **Invariant** — Cross-sheet rule, master.xlsx içi sheet'ler arası kural. 20 CSR rule mevcut; her Excel write sonrası denetlenir.
- **Manager Session** — Karar verici Claude session'ı. Kod yazmaz; plan yapar, worker yönlendirir, ADR yazar.
- **Phase** — Roadmap'teki tek bir adım; kendi acceptance kriteri olan iş paketi.
- **Pilot Project** — v1 acceptance test'inde kullanılan proje, **dentnotion** (ADR-003). Eski `~/Documents/platinum-premium-seo/` repo'sunda en olgun klasör.
- **Plugin** — `platinum-seo-engine` repo'su. Logic, skill, command, hook, schema barındıran proje-agnostik kısım.
- **Repo Hierarchy** — Plugin (logic) + Workspace (data/state) ayrımı. İki repo arası sözleşme spec §2.3'te.
- **Schema** — JSON Schema dosyası (`schemas/*.schema.json`); data shape kontratı. Schema-First disiplini gereği veri yazılmadan ÖNCE var olmalı.
- **Skill** — Doğal dil ile tetiklenen yetenek. Markdown dosyasında frontmatter + body olarak tanımlı.
- **Soak Period** — v1 acceptance sonrası eski repo'lar (`platinum-seo-core`, `platinum-premium-seo`) silinmeden önceki **1 haftalık** bug surface süresi (ADR-004). Bu süre boyunca eski dosyalar READ-ONLY referans.
- **Worker Session** — Manager tarafından dispatch edilen, dar scope'lu Claude session'ı. Manager'ın belirlediği görevi tek başına yapar.
- **Workflow** — Multi-step bir skill'in çalışma süreci. State `workflow-run.schema.json`'a uygun JSON ile tutulur (resume/retry/approval gate destekli).
- **Workspace** — `platinum-seo-workspace` repo'su. Proje verisi, state, output, raw data tutar; logic içermez.
