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
