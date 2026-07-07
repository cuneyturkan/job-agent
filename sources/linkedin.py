"""LinkedIn halka açık (giriş gerektirmeyen) iş arama kaynağı.

LinkedIn'in misafir arama endpoint'ini kullanır:
https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search

Not: Bu endpoint resmi bir API değildir; LinkedIn yapıyı değiştirirse
parser'ın güncellenmesi gerekebilir. Giriş yapılmadığı için hesabınla
ilgili bir risk yoktur.
"""

import hashlib
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _job_id(url: str) -> str:
    """URL'den kararlı bir kimlik üret (takip parametrelerini at)."""
    clean = url.split("?")[0]
    return "li-" + hashlib.sha1(clean.encode()).hexdigest()[:16]


def fetch(keywords: str, location: str = "", time_window: int = 86400,
          max_pages: int = 2, session: requests.Session | None = None) -> list[dict]:
    """Tek bir sorgu için ilanları döndür."""
    sess = session or requests.Session()
    jobs = []

    for page in range(max_pages):
        params = {
            "keywords": keywords,
            "f_TPR": f"r{time_window}",   # son X saniye
            "start": page * 25,
        }
        if location:
            params["location"] = location

        try:
            resp = sess.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
        except requests.RequestException as exc:
            print(f"[linkedin] ağ hatası ({keywords!r}): {exc}")
            break

        if resp.status_code == 429:
            # Hız sınırı — biraz bekle ve bu sorguyu bırak
            print(f"[linkedin] 429 rate limit ({keywords!r}), sorgu atlandı")
            time.sleep(5)
            break
        if resp.status_code != 200 or not resp.text.strip():
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("li")
        if not cards:
            break

        for card in cards:
            link = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")
            title_el = card.select_one("h3.base-search-card__title") or card.select_one("h3")
            company_el = card.select_one("h4.base-search-card__subtitle") or card.select_one("h4")
            loc_el = card.select_one("span.job-search-card__location")
            date_el = card.select_one("time")

            if not link or not title_el:
                continue

            url = link.get("href", "").strip()
            if not url:
                continue

            jobs.append({
                "id": _job_id(url),
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "?",
                "location": loc_el.get_text(strip=True) if loc_el else (location or "—"),
                "url": url.split("?")[0],
                "posted": date_el.get("datetime", "") if date_el else "",
                "source": "LinkedIn",
            })

        # Sayfa dolu değilse devam etmeye gerek yok
        if len(cards) < 25:
            break
        time.sleep(2)  # sayfalar arası nazik bekleme

    return jobs
