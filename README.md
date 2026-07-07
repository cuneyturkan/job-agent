# ✈️ İş İlanı Ajanı

Günde 2 kez (TR saatiyle 09:00 ve 18:00) LinkedIn'in halka açık iş aramasını + Daijob, CareerCross ve JSfirm'i tarar; **daha önce bildirmediği** ve senin kriterlerine uyan ilanları Telegram'dan gönderir.

Kategoriler:
1. 🇯🇵 Japonya'daki havacılık firmaları
2. ✈️ Lessor technical representative / redelivery / records işleri (dünya geneli + remote)
3. 🏢 Japonya'da havacılık dışı planlama / orta düzey yöneticilik

---

## Kurulum (yaklaşık 15 dakika)

### 1. Telegram botu oluştur

1. Telegram'da **@BotFather**'ı aç → `/newbot` yaz.
2. Bota bir isim ve kullanıcı adı ver (örn. `cuneyt_is_ajani_bot`).
3. BotFather sana bir **token** verecek (`123456789:AAF...` gibi). Bunu kaydet.
4. Yeni botunu aç ve ona herhangi bir mesaj gönder (örn. "merhaba"). **Bu adım şart**, yoksa bot sana yazamaz.

### 2. Chat ID'ni öğren

Tarayıcıda şu adresi aç (TOKEN yerine kendi token'ını yaz):

```
https://api.telegram.org/botTOKEN/getUpdates
```

Dönen JSON'da `"chat":{"id":123456789...` kısmındaki sayı senin **chat ID**'in. (Boş dönerse bota tekrar mesaj at ve sayfayı yenile.)

### 3. GitHub reposu oluştur

1. GitHub'da **yeni bir private repo** aç (örn. `job-agent`).
2. Bu klasördeki tüm dosyaları repoya yükle (git ile push'la veya web arayüzünden "Add file → Upload files").
   - `.github/workflows/job-agent.yml` dosyasının klasör yapısıyla birlikte gittiğinden emin ol.

### 4. Secrets ekle

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret adı | Değer |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather'ın verdiği token |
| `TELEGRAM_CHAT_ID` | 2. adımdaki sayı |

### 5. İlk test

Repo → **Actions** sekmesi → soldan **Job Agent** → sağda **Run workflow** → Run.

1-2 dakika içinde Telegram'a ilk ilanlar düşmeli. İlk çalıştırma en kalabalık olanıdır (son 24 saatin tüm ilanları); sonrakiler sadece yenileri gönderir.

> Actions ilk kez schedule ile çalışmıyorsa: repo yeni oluşturulduysa GitHub bazen ilk manuel tetiklemeden sonra zamanlamayı aktive eder. Bir kez elle çalıştırman yeterli.

---

## Özelleştirme

Her şey `config.yaml` içinde:

- **Yeni arama eklemek:** ilgili kategorinin `linkedin_queries` listesine satır ekle.
- **Gürültüyü azaltmak:** `exclude_keywords` listesine kelime ekle (başlıkta geçerse ilan elenir).
- **Daha fazla/az ilan:** `max_jobs_per_run` değerini değiştir.
- **Kaynak kapatmak:** `extra_sources` altında `enabled: false` yap.
- **Saatleri değiştirmek:** `.github/workflows/job-agent.yml` içindeki cron satırları (UTC olduğunu unutma, TR = UTC+3).

Değişiklikleri commit'lediğinde bir sonraki çalışmada devreye girer.

## Bilinmesi gerekenler

- **LinkedIn:** Giriş yapılmadan, halka açık arama sayfası okunur — hesabınla ilgili risk yok. Resmi API olmadığı için LinkedIn sayfa yapısını değiştirirse `sources/linkedin.py` güncellenmesi gerekebilir. Bir gün ilan gelmemeye başlarsa Actions log'una bak.
- **Daijob / CareerCross / JSfirm:** Best-effort parser'lar. Site yapısı değişirse o kaynak sessizce boş döner, log'da uyarı görürsün; ajan çökmez.
- **`state/seen.json`:** Bildirilen ilanların listesi. Workflow her çalışmada bunu repoya commit'ler; böylece aynı ilan iki kez gelmez. Silersen her şey "yeni" sayılır.
- **GitHub Actions ücretsiz limiti:** Private repoda ayda 2000 dakika. Bu ajan çalıştırma başına ~2-3 dakika kullanır (günde 2 × 30 gün ≈ 180 dk/ay) — fazlasıyla yeter.

## Sorun giderme

| Belirti | Muhtemel neden |
|---|---|
| Telegram'a hiç mesaj gelmiyor | Secrets yanlış, ya da bota hiç mesaj atmadın (1. adım 4. madde) |
| "429 rate limit" logları | LinkedIn geçici olarak yavaşlattı; bir sonraki çalışmada düzelir |
| Bir kaynaktan hep 0 ilan | Site yapısı değişti; log'daki uyarıya bak |
| Çok alakasız ilan geliyor | `include_keywords` / `exclude_keywords` listelerini sıkılaştır |
