# -*- coding: utf-8 -*-
import os
import ssl
import subprocess
import tempfile
import urllib.request


def _log(logger, level, message):
    if not logger:
        return
    log_fn = getattr(logger, level, None)
    if callable(log_fn):
        log_fn(message)


def fetch_text(url, headers=None, scraper=None, logger=None, timeout=20, use_windows_curl_fallback=True):
    request_headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": url,
    }
    if headers:
        request_headers.update(headers)

    if scraper is not None:
        try:
            response = scraper.get(url, timeout=timeout, headers=request_headers)
            if response.status_code == 200:
                return response.text
            _log(logger, "error", f"HTTP {response.status_code} for {url}")
        except Exception as exc:
            _log(logger, "warning", f"Scraper request failed: {exc}")

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=request_headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            if 200 <= response.status < 300:
                return response.read().decode("utf-8", errors="ignore")
            _log(logger, "error", f"urllib HTTP {response.status} for {url}")
    except Exception as exc:
        _log(logger, "warning", f"urllib request failed: {exc}")

    if not (use_windows_curl_fallback and os.name == "nt"):
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
            tmp_path = tmp_file.name

        command = [
            "curl.exe",
            "-L",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "10",
            "--max-time",
            str(timeout),
            "--user-agent",
            request_headers.get("User-Agent", "Mozilla/5.0"),
            "--referer",
            request_headers.get("Referer", url),
            "-o",
            tmp_path,
            url,
        ]

        startupinfo = None
        creationflags = 0
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout + 10,
            check=False,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        if completed.returncode == 0 and tmp_path and os.path.exists(tmp_path):
            with open(tmp_path, "rb") as fh:
                data = fh.read()
            if data:
                return data.decode("utf-8", errors="ignore")

        stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
        _log(logger, "error", f"curl.exe failed rc={completed.returncode}: {stderr[:200]}")
    except Exception as exc:
        _log(logger, "error", f"curl.exe request failed: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return None
