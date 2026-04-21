# AdultHideout Repository

![Adulthideout 10th Anniversary](repository.adulthideout/resources/fanart.jpg)

## 1.0.9 "Cloud Nine" - 10th Anniversary Year Expansion

AdultHideout started in **January 2016** as a tiny personal addon for a single site: Motherless. One site became a few, a few became dozens, and somehow 10 years went by.

**2026** is AdultHideout's **10th Anniversary Year**. Version **1.0.7 "Lucky 7"** kicked it off with 50 new sites, **1.0.8 "Jubilee Year Update"** stabilized the expansion, and **1.0.9 "Cloud Nine"** continues the celebration with **10 new sites**, new resolver work, API-based providers, Cloudflare-hardening, and several difficult playback fixes.

### 1.0.9 New Sites
ArchiveBate, CamCaps, Chaturbate, HentaiDude, HentaiOcean, Ikisoda, JAVHDPorn, Perverzija, PMVHaven, XOpenload.

### 1.0.9 Highlights

**Chaturbate returns**, paired with **ArchiveBate** - the addon now covers both sides: live rooms and archived cam recordings. Chaturbate includes categories, search, pagination, right-click filters and a dedicated live-room playback path. ArchiveBate adds gender filters, sorting and a local proxy-cache for CDN-protected thumbnails.

**CamCaps** was trickier than it looked - many entries route through external hosters (mostly Lulu), so the addon filters and resolves them carefully with hardened playback paths.

**JAVHDPorn** was the hardest one. It sits behind Cloudflare-style protection and mixes several hoster/player layers, so it needed Cloudflare-aware fetching, a StreamTape/HugStream resolver, and playback fixes so it behaves in Kodi the same way it does in a browser.

**Perverzija, HentaiOcean, Ikisoda and XOpenload** brought more resolver and API work: Cloudflare-hardened listings with XtremeStream HLS, API/RSS-based flows with direct MP4, KVS-style playback, and full-length movie support via small vendored hoster ports.

**Stability:** AVJoy now has page/session/stream caching, curl-based fetch paths, pre-resolving and a seek-aware local proxy for slow CDN streams. WatchPorn dropped its fragile local proxy in favor of stable direct header-based playback.

---

## Installation / Update

You can install the **AdultHideout Repository** using one of the methods below. Once the repository is installed, you can install or update the video addon from it.

### Method 1: File Manager Source
1. Open Kodi and select the **Gear Icon**.
2. Go to **File manager** -> **Add source**.
3. Click `<None>` and enter: `https://vashiel.github.io/repository.adulthideout/`
4. Name the source `AdultHideout` and click **OK**.
5. Return to Kodi and open **Add-ons**.
6. Click the **Package Icon**.
7. Select **Install from zip file** -> `AdultHideout` -> `repository.adulthideout-1.0.4.zip`.
8. Then go to **Install from repository** -> **Adulthideout Video Addon Repository** -> **Video add-ons** -> **AdultHideout**.

### Method 2: Direct ZIP Download
1. Download the repository ZIP:
   [Download repository.adulthideout-1.0.4.zip](https://github.com/Vashiel/repository.adulthideout/raw/master/repository.adulthideout-1.0.4.zip)
2. Open Kodi -> **Add-ons** -> **Package Icon** -> **Install from zip file**.
3. Select the downloaded `repository.adulthideout-1.0.4.zip`.
4. Then install **AdultHideout** from the repository.

### Method 3: Downloader App (Fire TV / Android TV)
1. Open the **Downloader** app.
2. Enter the shortcode **`9480267`** or `aftv.news/9480267`.
3. Download `repository.adulthideout-1.0.4.zip`.
4. In Kodi, go to **Add-ons** -> **Package Icon** -> **Install from zip file**.
5. Install the repository ZIP, then install **AdultHideout** from the repository.

---

## Repository Links

- **Homepage / ZIP**: [https://vashiel.github.io/repository.adulthideout/](https://github.com/Vashiel/repository.adulthideout/raw/master/repository.adulthideout-1.0.4.zip)
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

### 1.0.8 "Jubilee Year Update" - 2026-03-31
- Broad repair pass across site adapters, playback paths, pagination, thumbnails and navigation
- Expanded KVAT validation coverage
- Cleanup after the 1.0.7 expansion
- Removed `RealCuckoldSex` (domain became a sale/parking page) and `TubeDupe` (site only serves fixed 6-minute clips)

### 1.0.7 "Lucky 7" - 2026-03-06
**50 New Sites**: PornDoe, PornOne, PornHat, PornTrex, CumLouder, PornMZ, AnySex, PornDig, Tube8, xCafe, LetMeJerk, Upornia, FullPorner, XXXFiles, 3Movs, PornHD3X, XMoviesForYou, Porn300, OK.xxx, PerfectGirls, SuperPorn, XBabe, Veporn, Porn7, Porn00, Tubev, HClips, ThePornBang, BravoPorn, PornSlash, Pornheed, HDZog, ZBPorn, TrendyPorn, Nudez, Pornwhite, Pornflip, PornTry, BananaMovies, SaintPorn, WatchPorn, BigAssPorn, FPO, TheyAreHuge, BigTitsLust, BlackPorn24, MilfPorn8, MaturePorn.Tube, Blowjobs.pro, LesbianPorn8.

### 1.0.6 "Nautilus" - 2026-02-09
- Added 9 new sites
- Unified sorting across major providers
- Major updates for Redtube, Spankbang, Xhamster, XVideos, and YouPorn
- Stronger support for channels, collections, and pornstar navigation

### 1.0.5 "Massive Expansion" - 2026-01-13
- Added 14 new sites
- Complete Erome overhaul
- Large cleanup pass across the website adapters

### 1.0.4 "Gonzales" - 2025-11-25
- Added 9 new sites
- Introduced the internal proxy framework and vendored networking libraries
- Significant playback startup optimizations

### 1.0.0 "Jubilee"
- Unified BaseWebsite core
- Added DaftPorn, ePorner, MissAV, Pornhub, PornTN, and TubePornClassic
- Introduced dynamic menus, filters, and centralized query history

### Project Note - 2023-01-05
If anyone was wondering why I was away from AdultHideout for a while: life got in the way, health had to come first, and access to my GitHub-linked email account was lost for some time. Access was restored, nothing major had been changed, and work resumed afterward.

</details>

---

## Contributing and Support

- Submit bugs or feature requests through the issue tracker.
- Pull requests are welcome.

AdultHideout started with Motherless. Ten years later, it is still here.
