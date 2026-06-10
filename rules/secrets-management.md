---
name: Secrets Management
status: enforced
applies_to: [plugin, workspace]
spec_section: "§8.7"
---

# Secrets Management

## Kural
API key, token, password ve diğer hassas değerler ASLA repo'ya commit edilmemelidir. Secret'lar SADECE `.env` (gitignored) veya sistem keychain üzerinden okunur. `.env.example` placeholder dosyası commit edilir; gerçek değer içermez. Pre-commit hook (`scripts/security/check_secrets.sh`) her commit'i otomatik tarar ve sızıntı tespit ederse commit'i REDDETMELİDİR.

## Why
Tek bir hardcoded API key sızıntısı projenin tüm GSC/DFS/MCP entegrasyonlarını yanmış sayar; rotation maliyetlidir, faturayı bilinmeyen aktörler şişirebilir, drift envanteri kayar. Spec §8.7 secret yönetimini "10 pazarlık edilemez kural"dan biri olarak konumlandırır: secret'ın **tek kaynağı** runtime ortamıdır, repo değil.

## How to Apply
- `.env` dosyası `.gitignore` içinde MUST listelenir; her plugin ve workspace'te.
- `.env.example` her zorunlu key için placeholder + yorum içermelidir (örn. `OPENAI_API_KEY=  # platform.openai.com/api-keys`).
- Kod secret'ı her zaman runtime'dan okur: `os.environ["X"]` veya `process.env.X`. Eksikse fail-fast (clear error).
- Pre-commit hook secret pattern'lerini (sk-, ghp_, AKIA, vb.) ve `.env` dosyalarının staging'e girmesini bloklar.
- CI pipeline aynı tarama mantığını PR üzerinde tekrar koşar (defense in depth).
- Sızıntı tespit edilirse: rotate → audit → incident note (DECISIONS).

## Examples (Doğru)
```python
# config.py
import os
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not configured (.env missing?)")
```

```bash
# .env.example (commit edilir)
OPENAI_API_KEY=        # https://platform.openai.com/api-keys
GSC_SERVICE_ACCOUNT=   # path to JSON keyfile
```

## Anti-Patterns (Ihlal)
```python
# YASAK — hardcoded secret
OPENAI_API_KEY = "sk-proj-AbCdEf123..."  # commit'te yakalanır
```

```bash
# YASAK — gerçek .env commit
git add .env  # pre-commit hook reject eder
```

```python
# YASAK — secret'i log'a yazma
logger.info(f"Calling API with key={api_key}")
```

## Enforcement
- **Pre-commit hook:** `scripts/security/check_secrets.sh` (Phase 3'te yazılacak; staged dosyalarda regex tarar, `.env` dosyalarını bloklar).
- **CI check:** PR pipeline aynı taramayı host'lanmış runner'da koşar; FAIL → merge bloklu.
- **Manuel review:** Code review checklist'inde "secret leak?" maddesi var.
- **Cross-link:** `→ rules/single-source-of-truth.md` (secret tek kaynağı `.env`'dir, ikinci yere yazılmaz).

## Base64 Yüksek-Entropi Sezgisi (kapsam + sınır)

Spesifik prefix'li 16 secret sınıfının (AIza, `sk-`, `ghp_`, AKIA, `xox`, PEM, DataForSEO, …) yanında, kanonik tarayıcı (`scripts/security/check_secrets.sh`, etiket `base64_high_entropy_secret_assignment`) **jenerik bir base64 sezgisi** de taşır. Tetikleyici: secret-ish bir anahtar adı (`key|token|secret|password|credential`) + atama + **tırnaklı, padding'li** bir base64 değer (≥24 base64 karakter + `=`/`==`). Örn. `api_key = "QUJDREVG…WVo="`.

**Neden padding şart (kesinlik çıpası):** base64 `=` dolgusunu yalnız gerçek base64 (uzunluğu 3'e bölünmeyen) taşır; hex hash'ler (md5/sha), git SHA'ları, uzun tanımlayıcılar ve tırnaklı dosya yolları **asla** `=` içermez. Bu repo hash-zincirli defterlerle dolu olduğundan, çıplak `[A-Za-z0-9+/]{24,}` deseni 195 zararsız yolu yanlış-pozitif yakalardı; `=` çıpası bunları yapısal olarak eler (tüm-repo taraması 0 FP).

**Bilinçli recall sınırı (limitasyon):** Padding'siz, tamamı harf-rakam (alfanümerik) bir base64 değeri regex açısından bir tanımlayıcıdan/hash'ten **ayırt edilemez**. grep ERE Shannon-entropisi hesaplayamaz (büyük/küçük harf + rakam karışımı tek bir ERE'de güvenle ifade edilemez), bu yüzden bu durum **kasıtlı olarak işaretlenmez** — işaretlemek hash/yol yanlış-pozitiflerini geri getirir. Bu amaçta gerçek araç bir entropi tabanlı tarayıcıdır (ör. `gitleaks` / `trufflehog` / `detect-secrets`); jenerik base64 tespiti gerekirse opsiyonel defense-in-depth olarak önerilir. Tek-kaynak: desen yalnız `check_secrets.sh` PATTERNS'tedir; CI wrapper, PreToolUse `--scan-stdin` geçidi ve event redaktörü onu aynalar.
