<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/tech-seo-governance.md (hreflang reciprocity / code & x-default validity / locale consistency), rules/schema-first.md, rules/events-writer.md, rules/append-only-state.md
-->
# hreflang / i18n Audit — $project_slug

**Tarih:** $date
**Sonuç:** $verdict
**Küme sayısı:** $cluster_count · **Bulgu:** $findings_total

> Recommendation-only (per tech-seo-governance hreflang rules): bu rapor
> önerilerdir; hreflang/`<head>`/sitemap düzeltmelerini **operatör** uygular.
> Motor hreflang üretmez, istemci altyapısına yazmaz.

## NOT_APPLICABLE notu (tek dilli site)

$not_applicable_note

> Tek dilli portföyde (tr-TR / en-CA / en-NG) hreflang yokluğu **doğrudur** —
> kusur değil. Bu kontrol stray/çelişkili hreflang olmadığını ucuza doğrular;
> çok-dilli bir müşteri imzalandığında kümeleri tam doğrular.

## Bulgular

$findings_table

> Karar mantığı (per tech-seo-governance hreflang rules): tek-yönlü çift = HIGH
> (Google yok sayar); self-reference / mutlak-olmayan URL / geçersiz kod = MEDIUM;
> noindex / self-canonical-olmayan / non-200 dönüş hedefi = HIGH (kümeyi kırar);
> çok-dilli kümede x-default eksik = LOW.

## AMBER uyarıları

$amber_warnings

## Kanıt zinciri

- Tarih: `$date` · Proje: `$project_slug` · Sonuç: `$verdict`
- Run ID: `$run_id`
- Yazıldı: `master.xlsx#robots_txt` (HF- prefix, sheet_merge idempotent)

> Üretildi: `hreflang-audit` skill — `scripts/discovery/hreflang_audit_transform.py`
> (FREE; SF hreflang_all + canonicals + internal export'tan, paid MCP yok).
