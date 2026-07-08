"""İş Ajanı — LinkedIn + iş sitelerini tarar, yeni ve uygun ilanları
Telegram'a gönderir.

Çalışma mantığı:
1. config.yaml içindeki kategorileri ve sorguları oku
2. state/seen.json içindeki daha önce bildirilmiş ilanları oku
3. Kaynakları tara, yeni ilanları anahtar kelime filtresinden geçir
4. Telegram'a kategori bazında gönder
5. seen.json'u güncelle (workflow bunu repoya commit'ler)
"""

import html
import json
import os
import sys
import time
from pathlib import Path

import requests
import yaml

from sources import linkedin
from sources.boards import fetch_extra

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state" / "seen.json"
MAX_SEEN = 5000  # dosya şişmesin diye en eski kayıtlar atılır


# ----------------------------------------------------------------
# Durum (daha önce görülen ilanlar)
# ----------------------------------------------------------------
def load_seen() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("[state] seen.json bozuk, sıfırdan başlanıyor")
    return {}


def save_seen(seen: dict) -> None:
    # En yeni MAX_SEEN kaydı tut
    items = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:MAX_SEEN]
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(dict(items), ensure_ascii=False, indent=0),
        encoding="utf-8",
    )


# ----------------------------------------------------------------
# Filtreleme
# ----------------------------------------------------------------
def passes_filter(job: dict, include: list[str], exclude: list[str]) -> bool:
    title = job["title"].lower()
    for kw in exclude:
        if kw.lower() in title:
            return False
    if not include:
        return True
    return any(kw.lower() in title for kw in include)


# ----------------------------------------------------------------
# Telegram
# ----------------------------------------------------------------
def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanımlı değil!")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"[telegram] HTTP {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except requests.RequestException as exc:
        print(f"[telegram] ağ hatası: {exc}")
        return False


def format_job(job: dict) -> str:
    title = html.escape(job["title"])
    company = html.escape(job.get("company") or "?")
    loc = html.escape(job.get("location") or "—")
    line = f"• <a href=\"{job['url']}\">{title}</a>"
    extras = []
    if company != "?":
        extras.append(company)
    if loc and loc != "—":
        extras.append(loc)
    extras.append(job["source"])
    line += f"\n   <i>{html.escape(' | '.join(e for e in extras if e))}</i>"
    return line


def send_category(category_name: str, jobs: list[dict]) -> None:
    """Kategoriyi 4096 karakter sınırına göre parçalara bölerek gönder."""
    header = f"<b>{html.escape(category_name)}</b> — {len(jobs)} yeni ilan\n\n"
    chunk = header
    for job in jobs:
        entry = format_job(job) + "\n\n"
        if len(chunk) + len(entry) > 3900:
            send_telegram(chunk.rstrip())
            time.sleep(1)
            chunk = header + entry
        else:
            chunk += entry
    if chunk.strip() != header.strip():
        send_telegram(chunk.rstrip())


# ----------------------------------------------------------------
# Ana akış
# ----------------------------------------------------------------
def run_test_mode(config: dict, settings: dict, seen: dict) -> int:
    """Test modu: filtreyi geçen İLK ilanı gönderir ve çıkar.

    Sadece o tek ilan seen.json'a yazılır; kalan ilanlar bir sonraki
    normal çalıştırmada eksiksiz gelir.
    """
    print("🧪 TEST MODU: tek ilan gönderilecek")
    session = requests.Session()
    for cat in config.get("categories", []):
        include = cat.get("include_keywords", []) or []
        exclude = cat.get("exclude_keywords", []) or []
        for q in cat.get("linkedin_queries", []):
            jobs = linkedin.fetch(
                keywords=q.get("keywords", ""),
                location=q.get("location", ""),
                time_window=settings.get("linkedin_time_window", 86400),
                max_pages=1,
                session=session,
            )
            for job in jobs:
                if job["id"] in seen or not passes_filter(job, include, exclude):
                    continue
                ok = send_telegram(
                    "🧪 <b>TEST BAŞARILI!</b> Ajan çalışıyor. Örnek ilan:\n\n"
                    + f"<b>{html.escape(cat['name'])}</b>\n\n"
                    + format_job(job)
                    + "\n\nNormal çalıştırmada tüm yeni ilanlar gelecek."
                )
                if ok:
                    seen[job["id"]] = int(time.time())
                    save_seen(seen)
                    print(f"Test ilanı gönderildi: {job['title']}")
                    return 0
                print("Telegram gönderimi başarısız — token/chat ID kontrol et.")
                return 1
    send_telegram("🧪 Test modu çalıştı ama son 24 saatte filtreyi geçen ilan bulunamadı. Kurulum yine de doğru demektir.")
    print("Test modu: uygun ilan bulunamadı ama akış tamamlandı.")
    return 0


def main() -> int:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    settings = config.get("settings", {})
    seen = load_seen()
    now = int(time.time())

    if os.environ.get("TEST_MODE", "").lower() == "true":
        return run_test_mode(config, settings, seen)

    new_by_category: dict[str, list[dict]] = {}
    run_ids: set[str] = set()  # aynı çalıştırma içinde mükerrer engelleme
    total_new = 0
    max_jobs = settings.get("max_jobs_per_run", 40)

    session = requests.Session()

    # --- LinkedIn kategorileri ---
    for cat in config.get("categories", []):
        name = cat["name"]
        include = cat.get("include_keywords", []) or []
        exclude = cat.get("exclude_keywords", []) or []

        for q in cat.get("linkedin_queries", []):
            jobs = linkedin.fetch(
                keywords=q.get("keywords", ""),
                location=q.get("location", ""),
                time_window=settings.get("linkedin_time_window", 86400),
                max_pages=settings.get("linkedin_max_pages", 2),
                session=session,
            )
            print(f"[linkedin] '{q.get('keywords')}' ({q.get('location') or 'her yer'}): {len(jobs)} ilan")

            for job in jobs:
                if job["id"] in seen or job["id"] in run_ids:
                    continue
                if not passes_filter(job, include, exclude):
                    continue
                run_ids.add(job["id"])
                new_by_category.setdefault(name, []).append(job)
                total_new += 1
            time.sleep(2)

    # --- Ek kaynaklar ---
    for src_name, src_cfg in (config.get("extra_sources") or {}).items():
        if not src_cfg.get("enabled", False):
            continue
        jobs = fetch_extra(src_name, src_cfg.get("queries", []))
        print(f"[{src_name}] toplam {len(jobs)} ilan")
        cat_name = src_cfg.get("category", src_name)
        for job in jobs:
            if job["id"] in seen or job["id"] in run_ids:
                continue
            run_ids.add(job["id"])
            new_by_category.setdefault(cat_name, []).append(job)
            total_new += 1

    # --- Gönderim ---
    # ÖNEMLİ: Bir ilan yalnızca GÖNDERİLDİYSE seen.json'a yazılır.
    # max_jobs_per_run sınırına takılan ilanlar görülmemiş sayılır ve
    # bir sonraki çalıştırmada gönderilir.
    if total_new == 0:
        print("Yeni ilan yok, mesaj gönderilmiyor.")
    else:
        sent = 0
        for cat_name, jobs in new_by_category.items():
            if sent >= max_jobs:
                break
            batch = jobs[: max_jobs - sent]
            send_category(cat_name, batch)
            for job in batch:
                seen[job["id"]] = now
            sent += len(batch)
            time.sleep(1)
        if total_new > sent:
            send_telegram(
                f"ℹ️ Toplam {total_new} yeni ilan bulundu, bu sefer {sent} tanesi "
                f"gönderildi. Kalan {total_new - sent} ilan bir sonraki çalıştırmada "
                f"gönderilecek. Tek seferde daha fazlası için: config.yaml → max_jobs_per_run."
            )
        print(f"Toplam {total_new} yeni ilan, {sent} gönderildi.")

    save_seen(seen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
