"""LinkedIn dışı iş siteleri (best-effort parser'lar).

Bu siteler resmi API sunmadığı için HTML yapıları üzerinden okunur.
Herhangi biri yapısını değiştirirse o kaynak o çalıştırmada sonuç
döndürmez ve log'a uyarı yazılır — ajan çökmez, diğer kaynaklarla
devam eder.
"""

import hashlib
import time
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _jid(prefix: str, url: str) -> str:
    return prefix + "-" + hashlib.sha1(url.split("?")[0].encode()).hexdigest()[:16]


def _get(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        if resp.status_code != 200:
            print(f"[boards] {url} -> HTTP {resp.status_code}")
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        print(f"[boards] ağ hatası: {url} -> {exc}")
        return None


# ---------------------------------------------------------------
# Daijob — Japonya'da yabancılara/iki dilli adaylara yönelik ilanlar
# ---------------------------------------------------------------
def fetch_daijob(query: str) -> list[dict]:
    url = f"https://www.daijob.com/en/jobs/search_result?job_search_form_hidden=1&keywords={quote_plus(query)}"
    soup = _get(url)
    if soup is None:
        return []

    jobs = []
    # İlan kartları: başlık linkleri /en/jobs/detail/ içerir
    for a in soup.select("a[href*='/en/jobs/detail/']"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or len(title) < 4 or not href:
            continue
        full = urljoin("https://www.daijob.com", href)
        jobs.append({
            "id": _jid("dj", full),
            "title": title,
            "company": "?",
            "location": "Japan",
            "url": full,
            "posted": "",
            "source": "Daijob",
        })

    # Aynı ilana giden çoklu linkleri temizle
    seen, out = set(), []
    for j in jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            out.append(j)
    if not out:
        print(f"[daijob] '{query}' için sonuç bulunamadı (yapı değişmiş olabilir)")
    return out[:15]


# ---------------------------------------------------------------
# CareerCross — Japonya, iki dilli profesyonel ilanlar
# ---------------------------------------------------------------
def fetch_careercross(query: str) -> list[dict]:
    url = f"https://www.careercross.com/en/job-search?keywords={quote_plus(query)}"
    soup = _get(url)
    if soup is None:
        return []

    jobs = []
    for a in soup.select("a[href*='/en/job/detail-']"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or len(title) < 4 or not href:
            continue
        full = urljoin("https://www.careercross.com", href)
        jobs.append({
            "id": _jid("cc", full),
            "title": title,
            "company": "?",
            "location": "Japan",
            "url": full,
            "posted": "",
            "source": "CareerCross",
        })

    seen, out = set(), []
    for j in jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            out.append(j)
    if not out:
        print(f"[careercross] '{query}' için sonuç bulunamadı (yapı değişmiş olabilir)")
    return out[:15]


# ---------------------------------------------------------------
# JSfirm — havacılık odaklı iş sitesi (lessor/records/rep işleri
# burada sık görülür)
# ---------------------------------------------------------------
def fetch_jsfirm(query: str) -> list[dict]:
    url = f"https://www.jsfirm.com/search/results?keywords={quote_plus(query)}"
    soup = _get(url)
    if soup is None:
        return []

    jobs = []
    for a in soup.select("a[href*='/job/']"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or len(title) < 4 or not href:
            continue
        full = urljoin("https://www.jsfirm.com", href)
        jobs.append({
            "id": _jid("js", full),
            "title": title,
            "company": "?",
            "location": "",
            "url": full,
            "posted": "",
            "source": "JSfirm",
        })

    seen, out = set(), []
    for j in jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            out.append(j)
    if not out:
        print(f"[jsfirm] '{query}' için sonuç bulunamadı (yapı değişmiş olabilir)")
    return out[:15]


FETCHERS = {
    "daijob": fetch_daijob,
    "careercross": fetch_careercross,
    "jsfirm": fetch_jsfirm,
}


def fetch_extra(source_name: str, queries: list[str]) -> list[dict]:
    fn = FETCHERS.get(source_name)
    if fn is None:
        return []
    all_jobs = []
    for q in queries:
        all_jobs.extend(fn(q))
        time.sleep(2)
    return all_jobs
