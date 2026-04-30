---
name: Time Discipline
status: enforced
applies_to: [plugin, workspace]
spec_section: "§8.10"
---

# Time Discipline

## Kural
Tüm timestamp'ler **storage layer**inde UTC ISO 8601 formatında saklanmalıdır (`2026-04-30T12:34:56Z`). Excel hücreleri, JSONL event'leri, JSON state dosyaları, log satırları — kod-okunur her yer SADECE UTC içerir. Yerel saat (Europe/Istanbul) sadece **display layer**inde (rapor, dashboard, kullanıcıya gösterilen mesaj) çevrilir; storage'a yerel saat YAZILMAMALIDIR.

## Why
Workspace'ler farklı zaman dilimlerinde açılabilir; Excel'de bir hücre lokal saatle yazılır, başka bir cihazda farklı yorumlanırsa cross-sheet invariant'lar (örn. "monthly report dönem aralığı") kırılır. Türkiye 2016'dan beri DST'siz tek dilim (UTC+03:00) olsa bile workspace dosyaları taşınır, paylaşılır, CI runner'larda işlenir — UTC tek tutarlı zemindir. Spec §8.10 zaman'ı 10 pazarlık edilemez kural arasında sabitler.

## How to Apply
- Yeni timestamp üretirken: Python `datetime.now(timezone.utc).isoformat()` veya `datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")`.
- Excel'e yazarken: hücre değeri UTC string (`2026-04-30T12:34:56Z`); Excel'in tarih hücresi formatına bırakma (otomatik lokal yorumlar).
- Schema'larda timestamp alanları `format: "date-time"` (RFC 3339 / ISO 8601) ve regex `Z` suffix kontrolü.
- Display layer (monthly-report, dashboard skill'i) `pytz.timezone("Europe/Istanbul")` ile çevirip "30 Nisan 2026, 15:34" gibi insan-yüzlü çıktı verir; storage'a geri yazma.
- workflow run ID'leri: `{slug}-{YYYY-MM-DD}-{short_uuid}` — tarih kısmı UTC günü olmalı.

## Examples (Doğru)
```python
# storage layer — UTC
from datetime import datetime, timezone
event = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "type": "skill_started"}
# events.jsonl: {"ts":"2026-04-30T12:34:56Z","type":"skill_started"}
```

```python
# display layer — UTC -> Europe/Istanbul
from zoneinfo import ZoneInfo
ts_utc = datetime.fromisoformat("2026-04-30T12:34:56+00:00")
ts_tr  = ts_utc.astimezone(ZoneInfo("Europe/Istanbul"))
print(ts_tr.strftime("%d %b %Y, %H:%M"))  # "30 Apr 2026, 15:34"
```

## Anti-Patterns (Ihlal)
```python
# YASAK — Excel'e lokal saat yaz
ws["A1"] = datetime.now().isoformat()  # offset yok, ambiguous
# baska bir runner UTC sanip yorumlar -> cross-region drift
```

```python
# YASAK — tz-naive timestamp storage
event["ts"] = datetime.now().isoformat()  # naive, Z yok
# events.jsonl tutarliligi bozulur
```

```python
# YASAK — display formatini storage'a yazma
event["ts"] = "30 Nisan 2026, 15:34"  # parse edilemez, drift
```

## Enforcement
- **Schema validation:** Timestamp alanları `pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"` ile kilitlenir; `tests/schemas/test_time_format.py` her PR'da koşar.
- **Excel invariant check:** `scripts/excel/transaction.py` write öncesi timestamp hücrelerinin UTC ISO formatını verify eder; uymayan write reject.
- **Drift-check skill'i:** `events.jsonl` tarama sırasında naive/lokal timestamp'leri AMBER raporlar.
- **Cross-link:** `→ rules/naming.md` (workflow run ID tarih segmenti UTC); `→ rules/excel-discipline.md` (Excel hücreleri UTC text olarak yazılır).
