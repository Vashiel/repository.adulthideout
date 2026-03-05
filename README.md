# ![Adulthideout Fan Art](repository.adulthideout/resources/fanart.jpg)

# Adulthideout Video Addon Repository

**Version 1.0.6 "Nautilus" — 2026-02-09**

This update, codenamed **"Nautilus"**, focuses on the **depth of navigation** and technical **refinement**. It introduces 9 new sites, a completely unified sorting engine, and major overhauls of the addon's most popular providers.

### Key Changes in v1.0.6
* **Expansion:** Added support for **9 new sites**, bringing the total to 66 specialized adapters:
  * Area51, BoundHub, Fuqer, GoPorn, HeavyFetish, Pervertium, PussySpace, Rapelust, and Smutr.
* **Unified Sorting:** Integrated a standard "Sort By" system across major sites (Newest, Top Rated, Most Viewed, etc.) accessible via the context menu.
* **Site Redesign:** Major updates and stability fixes for flagship providers including **Redtube**, **Spankbang**, **Xhamster**, **XVideos**, and **YouPorn**.
* **Navigation Depth:** Added core support for **Channels**, **Collections**, and enhanced **Pornstar** listings.
* **Scraper Robustness:** Improved metadata parsing and layout-compatibility for various long-standing providers.

---

**Version 1.0.5 “Massive Expansion” — 2026-01-13**

This update represents a **massive expansion** of the addon's capabilities, introducing 14 new sites, a completely rewritten Erome scraper, and a comprehensive codebase cleanup.

### Key Changes in v1.0.5
* **Expansion:** Added support for **14 new sites**, including:
  * Analdin, BdsmStreak, DrTuber, Empflix, **Erome**, PervClips, PorCore, Shameless, Shooshtime, SunPorno, SxyPrn, ThisVid, TnaFlix.
* **Erome Overhaul:** Complete rewrite with robust filters (Straight/Gay/Trans/Hentai), persistent search, and seamless pagination.
* **Refactoring:** Removed all debugging comments from **all 57 websites** for a clean, production-ready codebase.
* **Decoders:** Added new decoding logic for SunPorno and optimized existing ones.

---

## 📦Installation / Update

You can install the **AdultHideout Repository** using one of the three methods below. Once the repository is installed, you can easily install or update the video addon from it.

### Method 1: File Manager Source (Recommended)
1. Open Kodi and select the **Gear Icon** (Settings) at the top left.
2. Go to **File manager** → **Add source**.
3. Click on `<None>` and enter the exact URL: `https://vashiel.github.io/repository.adulthideout/`
4. Name the media source `AdultHideout` and click **OK**.
5. Return to the Kodi home screen and go to **Add-ons**.
6. Click the **Package Icon** (open box) at the top left.
7. Select **Install from zip file** → `AdultHideout` → click on `repository.adulthideout-1.0.4.zip`.
8. Once installed, go to **Install from repository** → **Adulthideout Video Addon Repository** → **Video add-ons** → **AdultHideout** and install it.

### Method 2: Direct ZIP Download
1. Download the latest repository ZIP file directly using your browser:
   👉 **[Download repository.adulthideout-1.0.4.zip](https://github.com/Vashiel/repository.adulthideout/raw/master/repository.adulthideout-1.0.4.zip)**
2. Transfer the file to your Kodi device if necessary.
3. Open Kodi and navigate to **Add-ons** → **Package Icon** → **Install from zip file**.
4. Browse to the folder where you downloaded the file and select `repository.adulthideout-1.0.4.zip`.
5. Finally, go to **Install from repository** → **Adulthideout Video Addon Repository** → **Video add-ons** → **AdultHideout** and install it.

### Method 3: Downloader App (For FireTV / Android TV)
If you are using an Amazon Fire TV Stick or Android TV with the **Downloader App**, you can use this quick shortcode:
1. Open the **Downloader** app on your device.
2. Enter the shortcode: **`9480267`** *(Alternatively, enter `aftv.news/9480267` in the URL field).*
3. Press **Go / Enter**. The download of `repository.adulthideout-1.0.4.zip` will start automatically.
4. Open Kodi, go to **Add-ons** → **Package Icon** → **Install from zip file** and locate the file in your device's `Downloader` folder.
5. Finish by going to **Install from repository** → **Adulthideout Video Addon Repository** → **Video add-ons** → **AdultHideout** and install it.

---

**Version 1.0.4 “Gonzales” — 2025-11-25**

This is the largest update since v1.0.0. Version 1.0.4 "Gonzales" focuses entirely on speed and optimization while adapting to modern website security mechanisms.

To bypass these protections, a new internal **Proxy Framework** and robust **Vendored Libraries** (Requests, Urllib3, Cloudscraper, JS2Py) have been implemented. While such security layers typically add latency, the architecture was heavily optimized to counter this effect. Video startup times have been reduced from approximately 14 seconds to **instant playback**.

### Key Changes in v1.0.4
* **Performance:** Implemented `proxy_utils.py` for efficient session handling and local proxy streaming.
* **New Content:** Added **9 new sites**: DarknessPorn, FullXCinema, NoodleMagazine, PornZog, PunishWorld, ShemaleZ, VJAV, VoyeurHit, and YouPorn.
* **Refactoring:** Extensive changes to core logic and adapters. See `changelog.txt` for the full technical breakdown.

---

##  What’s New in v1.0.0 "Jubilee"

* **Core refactor:** unified `BaseWebsite` class for HTTP, parsing, filtering & playback
* **Six new adapters:** DaftPorn, ePorner, MissAV, Pornhub, PornTN (+ decoder), TubePornClassic (+ decoder)
* **Legacy removal:** dropped old scripts, modules and JSON caches
* **Dynamic menus:** category, sort, duration & quality filters
* **Central query history** via `queries.json`
* **Enhanced error handling** to avoid silent failures

---

## 🔗 Repository Links

* **Homepage / ZIP**:
  [https://vashiel.github.io/repository.adulthideout/](https://github.com/Vashiel/repository.adulthideout/raw/master/repository.adulthideout-1.0.4.zip)
* **Source Code**:
  [https://github.com/Vashiel/repository.adulthideout](https://github.com/Vashiel/repository.adulthideout)
* **Issue Tracker**:
  [https://github.com/Vashiel/repository.adulthideout/issues](https://github.com/Vashiel/repository.adulthideout/issues)

---

## 🤝 Contributing & Support

* **Submit bugs** or **feature requests** via the Issue Tracker.
* **Pull requests** are welcome — please follow the existing code style.

---

*Enjoy AdultHideout v1.0.6 “Nautilus”!*


# Update 05.01.2023
If anyone was wondering why I haven't been working on AH... I couldn't. I got Corona two years ago and there were aftermaths that I had to work on for a while.

In short, I had other concerns. 

In the meantime, someone managed to get access to my email address linked to Github and locked me out of both. I have access again since this morning. Nothing was changed. Someone just wanted to annoy me. I will work on the project again in the coming days.

Cheers, Anton.

# AdultHideout
XXX Porn Adult Addon. Matrix and Leia compatible.<br />
The one and only official site for my Repo is this Github Page.
