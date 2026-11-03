import requests

__version__ = "1.2.71"


def create_scraper(sess=None, browser=None, **kwargs):
    s = sess if sess is not None else requests.Session()
    custom_ua = None
    if isinstance(browser, dict):
        custom_ua = browser.get("custom")

    ua = custom_ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
    s.headers.setdefault("User-Agent", ua)
    s.headers.setdefault(
        "Accept",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    )
    s.headers.setdefault("Accept-Language", "en-US,en;q=0.9")
    return s


class CloudScraper(requests.Session):
    def __init__(self, *args, **kwargs):
        super(CloudScraper, self).__init__(*args, **kwargs)
        self.headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
        )
