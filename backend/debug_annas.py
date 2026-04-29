"""
debug_libgen.py — test LibGen direct download using MD5 from Anna's Archive
    python debug_libgen.py
"""
import httpx  # pyre-ignore
from bs4 import BeautifulSoup  # pyre-ignore

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# MD5 from Anna's Archive for Atomic Habits EPUB (Penguin, clean copy)
md5 = "8df4ec30b9d346ea82c87ab9540a702d"

# LibGen fiction and non-fiction lookup endpoints
libgen_urls = [
    f"https://libgen.com.im/search.php?req={md5}&column=md5",
    f"https://libgen.st/search.php?req={md5}&column=md5",
    f"https://libgen.rs/search.php?req={md5}&column=md5",
]

print("=== Testing LibGen MD5 lookup ===\n")
for url in libgen_urls:
    print(f"URL: {url}")
    try:
        r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=10)
        print(f"  Status   : {r.status_code}")
        print(f"  Final URL: {r.url}")
        soup = BeautifulSoup(r.text, "html.parser")
        # Look for download links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(x in href for x in ("get.php", "download", "md5", "/book/")):
                print(f"  Link: [{a.get_text().strip()[:40]}] → {href[:120]}")
        print()
    except Exception as e:
        print(f"  Error: {e}\n")

# Also try the LibGen fiction search (some books are under /fiction/)
fiction_url = f"https://libgen.is/fiction/?q={md5}&column=md5"
print(f"URL: {fiction_url}")
try:
    r = httpx.get(fiction_url, headers=HEADERS, follow_redirects=True, timeout=10)
    print(f"  Status   : {r.status_code}")
    print(f"  Final URL: {r.url}")
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(x in href for x in ("get.php", "download", "md5", "/book/")):
            print(f"  Link: [{a.get_text().strip()[:40]}] → {href[:120]}")
except Exception as e:
    print(f"  Error: {e}")