# AdultHideout Repository

![Adulthideout 10th Anniversary](repository.adulthideout/resources/fanart.jpg)

## 1.0.12 "Signal Lock"

AdultHideout started in **January 2016** as a tiny personal Kodi addon for one site. In 2026 the project is in its **10th Anniversary Year**, and 1.0.12 stands as one of our most ambitious updates yet—introducing a completely redesigned engine architecture and a brand-new way to experience the adult web.

**Signal Lock** introduces the revolutionary **Global Search**, brings ten new premium sites into the fold, adds in-process download/recording capabilities via FFmpeg, and implements a unified KVS player framework.

### New Sites

AllowFlash, NotFans, WOW.xxx, XXThots, JAVSubbed.net, Sextb.net, Porn4Fans, YesPornVIP, Tgtsporn, PornMedium.

### Highlights

- **Global Search:** Search across multiple sources simultaneously with profile presets, progressive paging, and stable navigation.
- **In-Process Downloading:** Added dynamic "Video herunterladen" context actions backed by a robust FFmpeg recording engine.
- **Engine Evolution:** Created `KVSTubeWebsite`, a unified base class to handle KVS-powered sites with remarkable simplicity and speed.
- **85po Android Fix:** Solved Cloudflare 403 blocks on Android/Fire TV by reusing session state and local Range proxy streams.
- **LuxureTV Repair:** Rebuilt parsing to adapt to recent markup changes, preventing failures when video durations are missing.
- **NoodleMagazine Rework:** Rewrote video resolution to query official nmcorp player playlists, bypassing broken CDN links.
- **Cleaned Up:** Removed UFlash due to new login/paywall requirements.

### Feature Focus: Global Search — Unified Multi-Site Discovery

With 1.0.12, we are introducing a new way to explore content: **Global Search**. 

Instead of searching one website at a time, Global Search allows you to query multiple scraper sources simultaneously. 

Key features of the global search:
- **Profile Presets:** Search using predefined sets of sources (e.g., straight, gay, trans, hentai) to query only what you need.
- **Asynchronous & Progressive Paging:** Load results in stages with per-source limits, preventing slow-responding sites from bottlenecking the entire search.
- **State Persistence:** When returning from watching a video, the search results page loads instantly without a full re-scan, preserving the current page and scroll position.
- **Profile-Aware Caching:** Under-the-hood caching prevents repetitive network requests while keeping results up-to-date.
- **Play from Here Support:** Plays search results sequentially across different websites as a seamless playlist using Kodi's native player features.

This allows you to search across multiple sites from a single search interface in the addon.

---

## Installation / Update

You can install the **AdultHideout Repository** in Kodi and then install or update the video addon from it.

### Method 1: File Manager Source

1. Open Kodi and select the **Gear Icon**.
2. Go to **File manager** -> **Add source**.
3. Click `<None>` and enter: `https://vashiel.github.io/repository.adulthideout/`
4. Name the source `AdultHideout` and click **OK**.
5. Open **Add-ons** and click the **Package Icon**.
6. Select **Install from zip file** -> `AdultHideout` -> `repository.adulthideout-1.0.4.zip`.
7. Then go to **Install from repository** -> **Adulthideout Video Addon Repository** -> **Video add-ons** -> **AdultHideout**.

### Method 2: Direct ZIP Download

1. Download the repository ZIP:
   [repository.adulthideout-1.0.4.zip](https://github.com/Vashiel/repository.adulthideout/raw/master/repository.adulthideout-1.0.4.zip)
2. Open Kodi -> **Add-ons** -> **Package Icon** -> **Install from zip file**.
3. Select the downloaded `repository.adulthideout-1.0.4.zip`.
4. Then install **AdultHideout** from the repository.

### Method 3: Downloader App (Fire TV / Android TV)

1. Open the **Downloader** app.
2. Enter shortcode **`9480267`** or `aftv.news/9480267`.
3. Download `repository.adulthideout-1.0.4.zip`.
4. Install the repository ZIP in Kodi, then install **AdultHideout** from the repository.

---

## Repository Links

- **Homepage**: [https://vashiel.github.io/repository.adulthideout/](https://vashiel.github.io/repository.adulthideout/)
- **Repository ZIP**: [repository.adulthideout-1.0.4.zip](https://github.com/Vashiel/repository.adulthideout/raw/master/repository.adulthideout-1.0.4.zip)
- **Source Code**: [https://github.com/Vashiel/repository.adulthideout](https://github.com/Vashiel/repository.adulthideout)
- **Issue Tracker**: [https://github.com/Vashiel/repository.adulthideout/issues](https://github.com/Vashiel/repository.adulthideout/issues)

---

## Disclaimer

AdultHideout is a Kodi video addon repository. It does not host third-party videos on its own servers and is not affiliated with the websites supported by the addon.

Content, streams and metadata are provided by third-party websites. The operators of those sites are responsible for their own content.

For repository issues, use GitHub Issues. For copyright complaints regarding content hosted on GitHub, GitHub's standard DMCA/copyright process applies.

---

## Release Archive

<details>
<summary>Older release notes</summary>

### 1.0.11 "Night Shift" - 2026-05-29
- Added 85po.com, HStream, PremiumPorn, XXXTube, and WhereIsMyPorn.
- Expanded "Explore Similar" support to Rule34Video, XVideos, XNXX, SpankBang, Pornhub, HQPorner, and 85po.
- Reworked PremiumPorn and ThePornBang crypto handling with bundled pure-Python helpers.
- Improved seek-safe local Range proxy playback for several MP4/KVS/CDN streams.
- Fixed Pornhub related-video thumbnails and playback startup regressions.
- Fixed XVideos pagination after Sort By.
- Added localized official-source/install warnings.

### 1.0.10 "Afterglow" - 2026-05-22
- Added PornHoarder, SpeedPorn and YourLesbians.
- Improved Ashemaletube, Chaturbate, FreeOMovie, Ikisoda, JavHDPorn, LetMeJerk, NoodleMagazine, PMVHaven, Porn7, PornDoe, Pornhub, Rapelust and Rule34Video.
- Improved DoodStream, Lulu/LuluVDO, DirtyVideo/Netu and proxy playback paths.
- Removed PornHits after the domain stopped serving its original site.

### 1.0.9 "Cloud Nine" - 2026-04-20
- Added ArchiveBate, CamCaps, Chaturbate, HentaiDude, HentaiOcean, Ikisoda, JAVHDPorn, Perverzija, PMVHaven and XOpenload.
- Added new resolver/API work for cam, hentai/JAV and multi-hoster providers.
- Improved AVJoy and WatchPorn playback stability.

### 1.0.8 "Jubilee Year Update" - 2026-03-31
- Broad repair pass across site adapters, playback paths, pagination, thumbnails and navigation.
- Expanded KVAT validation coverage.
- Removed RealCuckoldSex and TubeDupe.

### 1.0.7 "Lucky 7" - 2026-03-06
- Added 50 new sites.
- Improved Hanime, PerfectGirls, SuperPorn, Rule34Video, Pornhub and several core UI/playback paths.

### 1.0.6 "Nautilus" - 2026-02-09
- Added 9 new sites.
- Reworked Redtube, Spankbang, Xhamster, XVideos and YouPorn.
- Added stronger sorting, channel, collection and metadata support.

### 1.0.5 "Massive Expansion" - 2026-01-13
- Added 14 new sites.
- Reworked Erome and cleaned up many site adapters.

### 1.0.4 "Gonzales" - 2025-11-25
- Added 9 new sites.
- Introduced the internal proxy framework and vendored networking libraries.
- Improved playback startup and seeking behavior.

### 1.0.0 "Jubilee"
- Unified BaseWebsite core.
- Added DaftPorn, ePorner, MissAV, Pornhub, PornTN and TubePornClassic.
- Introduced dynamic menus, filters and centralized query history.

</details>

---

## Contributing and Support

- Submit bugs or feature requests through the issue tracker.
- Pull requests are welcome.

AdultHideout started with Motherless. Ten years later, it is still here.
