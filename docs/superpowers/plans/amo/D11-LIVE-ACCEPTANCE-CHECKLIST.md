# D11 — AMO Canlı Kabul Checklist'i (build'i kapatan son adım)

> **Bu ne?** AMO v2.0 build'inin (Faz 0-4) tamamı kod olarak bitti + push'lu (suite 2312/0).
> Geriye **tek** şey kaldı: tüm zincirin senin **gerçek ortamlarında** bir kez canlı çalıştığını
> kanıtlamak. Bu checklist o kabul testidir. Tümü ✅ olduğunda AMO build resmen kapanır ve
> (istersen) scheduler armlanabilir.
>
> **Önemli (dürüst çerçeve):** AMO döngüsü (`/pseo-run` vb.) bugüne kadar canlı koşmadı —
> stub-harness ile test edildi, canlı değil (karar D11, [[project_amo_live_acceptance_deferred]]).
> Yani bu **gerçek bir entegrasyon testi**. Her adımda: **komutu çalıştır → "ne görmelisin"i
> karşılaştır → ✅ ya da ❌ işaretle.** Beklenmedik bir şey olursa **DURMA, bana (manager) raporla** —
> birlikte triage ederiz. Bir ❌ ayıp değil; D11'in amacı tam da bunları canlıda yakalamak.
>
> **Proje:** demo-furniture (GSC doğrulanmış). **Ortamlar:** VSCode · Claude Mac app · CLI.
> **Detaylı "ne göreceksin" yüzeyleri:** `docs/RUNBOOK-portfolio-recovery.md` (4e runbook) — bu
> checklist tetikleme + kabul akışına odaklanır, kurtarma detayları runbook'ta.

---

## Bölüm 0 — Hazırlık (bir kez, tek ortamda; ✅ olmadan devam etme)

| # | Yap | Ne görmelisin | ✅/❌ |
|---|---|---|---|
| 0.1 | Workspace bağlı mı: bir oturumda `/pseo-status` çağır | Aktif proje + bekleyen run'lar listelenir (ya da "NO_ACTIVE_PROJECT" → 0.2). HATA "PSEO_WORKSPACE_ROOT set edilmemiş" çıkarsa workspace env'ini bağla | ☐ |
| 0.2 | demo-furniture'yu aktif yap: `/pseo-active demo-furniture` | Aktif marker `demo-furniture`'ya geçer (`shared/active.json`) | ☐ |
| 0.3 | Portföyde demo-furniture var mı: `/pseo-status-portfolio` | Triage tablosunda `demo-furniture` satırı görünür (durumu ne olursa olsun) | ☐ |
| 0.4 | **Bütçe tavanlarını set et** — `shared/cost-ceilings.json` oluştur/düzenle: `{"gsc_calls": 500, "dfs_credits": 200, "image_spend": 50}` | Dosya yazıldı. (Gerçek günlük kotalarını koy — bunlar örnek. O5: scheduler bunlar olmadan armlanamaz.) | ☐ |
| 0.5 | **Maliyet tahminlerini set et** — `shared/cost-estimates.json`: `{"monthly": {"gsc_calls": 50, "dfs_credits": 10, "image_spend": 0}, "audit": {...}, ...}` | Dosya yazıldı (her workflow için kabaca bir tahmin) | ☐ |

> Not: `cost-ceilings.json` ve `cost-estimates.json` **operatör dosyaları** (şema yok, elle düzenlenir).
> Değerler senin gerçek GSC/DFS kotalarına göre — yukarıdakiler sadece biçim örneği.

---

## Bölüm 1 — Faz 0: Bağlama (oturum ↔ proje)

| # | Yap | Ne görmelisin | ✅/❌ |
|---|---|---|---|
| 1.1 | Yeni bir oturum aç (VSCode) | SessionStart banner'ı bağlı projeyi (demo-furniture) doğru gösterir; başka projenin verisine yazmaz | ☐ |
| 1.2 | İkinci bir pencerede farklı proje aç (varsa) | İki pencere birbirinin state'ini karıştırmaz (her oturum kendi projesine kilitli) | ☐ |

---

## Bölüm 2 — Faz 1: Orkestratör (çekirdek döngü) 🎯

| # | Yap | Ne görmelisin | ✅/❌ |
|---|---|---|---|
| 2.1 | `/pseo-run monthly demo-furniture` | Sıralı pipeline çalışır: gsc-pull → quick-wins + content-decay → monthly-report. Model MCP işini yapar, **her adımın çıktısı doğrulanır** (kimlik+içerik geçidi) | ☐ |
| 2.2 | Çıktıyı izle | Bir **coverage kaydı** yazılır (`projects/demo-furniture/_state/coverage/<run_id>.json`); verdict `pass` ya da `incomplete` | ☐ |
| 2.3 | Verdict `pass` değilse | **Türkçe tek-satır remediation** görünür (kopyala-yapıştır `/pseo-run … --resume` fix komutu) | ☐ |

> 🔬 Bu, build'in kalbi: niyet → garantili sıralı çalışma → her adımın çıktısının doğrulanması.
> Burada bir entegrasyon sorunu çıkarsa (CLI yolu, MCP yanıtı, transform) **bana raporla** — en olası
> sürpriz noktası burası (ilk canlı koşu).

---

## Bölüm 3 — Faz 2: Güvenlik + zorlama (D11'in özü) 🔒

Bu bölüm senin iki sert kuralının + denetçinin **canlı** ateşlendiğini kanıtlar.

| # | Yap | Ne görmelisin | ✅/❌ |
|---|---|---|---|
| 3.1 | **Denetçi:** bir workflow başlat ama bir adımı kasıtlı atla / yarıda bırak, sonra oturumu bitirmeye çalış | Stop-hook **bloklar** + eksik adımı + Türkçe `/pseo-run … --resume` fix komutunu gösterir (eksik iş zorla tamamlatılır) | ☐ |
| 3.2 | **Consent geçidi:** bir outward aksiyon dene — örn. Indexing/sitemap submit (`mcp__gsc__submit_sitemap`) ya da `git push` | **DENY** (exit 2) + tam kopyala-yapıştır `/pseo-approve … "<hedef>"` mesajı (onay olmadan dışarı hiçbir şey gitmez) | ☐ |
| 3.3 | `/pseo-approve …` ile o aksiyona **bu oturumda** consent ver, sonra aksiyonu tekrar dene | Aksiyon bu sefer **geçer** (consent defteri hash-chained, per-session) | ☐ |
| 3.4 | **(Opsiyonel) AI-disclosure:** bir blog HTML'ine "AI tarafından yazıldı" benzeri ibare koyup Bash/heredoc ile yazmayı dene | Dosya **karantinaya** alınır (`.BLOCKED-ai-disclosure`), canlı `.html` yüzeyden kalkar (Bash bypass'ı bile engellenir) | ☐ |

> 🔬 3.2 + 3.3 senin **Indexing-consent** sert kuralın; 3.4 **"AI yazdı" yasağı** sert kuralın — ikisi de
> kodda zorlanıyor. 3.1 denetçinin "eksik işi zorla tamamlat" sözü.

---

## Bölüm 4 — Faz 4: Portföy + bütçe + kill-switch (güvenlik zirvesi) 💰

| # | Yap | Ne görmelisin | ✅/❌ |
|---|---|---|---|
| 4.1 | `/pseo-status-portfolio` | Türkçe triage tablosu: her proje sağlıklı/eksik/başarısız/duraklatıldı/kayıt-yok + global bütçe bloğu (kullanım/tavan/kalan) | ☐ |
| 4.2 | `/pseo-run-portfolio monthly` (normal tavanlarla) | Portföy sırayla taranır; özet bloğu çalıştırıldı/atlandı/duraklatıldı sayar | ☐ |
| 4.3 | **Kill-switch:** `cost-ceilings.json`'da bir tavanı kasıtlı **çok düşük** yap (örn. `gsc_calls: 1`), sonra `/pseo-run-portfolio monthly` | Bir proje **`paused`** (bütçe tavanı aşıldı) + kalanlar **`not_run`** + tarama **DURUR** + Türkçe resume komutu. **Sessizce eksik çalışmaz.** Kısmi rezervasyonlar serbest bırakılır (sızıntı yok) | ☐ |
| 4.4 | Tavanı geri yükselt → `/pseo-run-portfolio monthly` tekrar | Kalan projeler işlenir (kaldığı yerden devam) | ☐ |
| 4.5 | **O5 arming geçidi:** önce bir tavanı **sil** (`cost-ceilings.json`'dan çıkar), sonra `/pseo-schedule arm monthly daily` | **REDDEDİLİR** — Türkçe "tavan boşken gözetimsiz program armlanamaz" + eksik kaynağı söyler + hiçbir şey yazılmaz | ☐ |
| 4.6 | Tüm tavanları geri koy → `/pseo-schedule arm monthly daily` → öngörülen günlük maliyeti gör → **"evet"** ile onayla | Önce projeksiyon gösterilir, ayrı bir adımda **açık consent** istenir; "evet" deyince armed olur (marker `shared/schedule.json`) | ☐ |
| 4.7 | `/pseo-schedule status` sonra `/pseo-schedule disarm` | Status armed'i + öngörülen maliyeti gösterir; disarm KAPATIR (marker silinmez, `armed=false` yazılır) | ☐ |

> 🔬 4.3 sistemin en kritik güvenlik davranışı: **bütçe biterse durur, sessizce bozulmaz.** 4.5 otonominin
> tavansız armlanamaması (O5). Detaylı "ne göreceksin" → 4e runbook §2 + §6.

---

## Bölüm 5 — 3 ortam matrisi (taşınabilirlik)

Çekirdek kontrolleri **her 3 ortamda** tekrarla (binding + döngü + bir geçit canlıda çalışıyor mu):

| Kontrol | VSCode | Mac app | CLI |
|---|---|---|---|
| Bağlama doğru (Bölüm 1.1) | ☐ | ☐ | ☐ |
| `/pseo-run monthly demo-furniture` çalışır (2.1) | ☐ | ☐ | ☐ |
| Consent geçidi DENY eder (3.2) | ☐ | ☐ | ☐ |
| `/pseo-status-portfolio` render eder (4.1) | ☐ | ☐ | ☐ |

> 🔬 "3-5 proje paralel, üç ortamda da" hedefinin kanıtı. Mac app'te terminal yok → komutlar app içinden;
> binding session-id marker'ıyla (env-var değil) çalışır (D9), bu yüzden üç ortamda da tutmalı.

---

## Bölüm 6 — Final sign-off

- **Tüm ✅ ise:** 🎉 **AMO v2.0 build KAPANDI.** Sistem senin ortamlarında kanıtlandı. Artık:
  - Scheduler **bilinçli** armlanabilir (O5 tavanlar + per-cadence consent ile) + dış tetikleme bağlanabilir (4e runbook §6).
  - 4g (self-upgrade versioning) opsiyonel — istediğinde manager'a yazdırırsın.
  - Sürüm/release kapanışı (version bump + RELEASE_NOTES + tag) gündeme gelebilir.
- **Herhangi bir ❌ varsa:** o adımı **manager'a (bana) raporla** — birlikte triage ederiz (reassign/parçala/düzelt). D11 tek seferde %100 geçmek zorunda değil; her ❌ bir sonraki fix batch'ini doğurur.

---

### Hızlı komut özeti (kopyala-yapıştır)

```
/pseo-active demo-furniture                 # 0.2  demo-furniture'yu aktif yap
/pseo-status                       # 1.1  bağlama + bekleyen run'lar
/pseo-run monthly demo-furniture            # 2.1  çekirdek döngü
/pseo-approve <action> "<target>"  # 3.3  outward aksiyona consent
/pseo-status-portfolio             # 4.1  portföy triyajı
/pseo-run-portfolio monthly        # 4.2/4.3  sweep (+ kill-switch testi)
/pseo-schedule arm monthly daily   # 4.5/4.6  arming (O5 + consent)
/pseo-schedule status | disarm     # 4.7
```

> Provenance: spec §7 Phase 4 + §8 (live-acceptance-before-arm), MANAGER.md D11, bootstrap §9.
> Bu doküman hiçbir runtime davranışı değiştirmez — bir kabul worksheet'idir.
