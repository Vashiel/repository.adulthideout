<p align="center">
  <img src="repository.adulthideout/resources/fanart.jpg" alt="AdultHideout" width="100%">
</p>

<h1 align="center">AdultHideout</h1>
<p align="center">
  <strong>Adult-oriented video discovery, playback, search, collections and downloads for Kodi.</strong>
</p>

AdultHideout began in **January 2016** as a small personal Kodi addon for a single website. Over a decade of continuous development, it has grown into a cross-platform media browser uniting more than **300 third-party sources** inside one cohesive Kodi interface.

AdultHideout does not host videos. It organizes publicly available listings and hands playback to Kodi while providing the tools a massive catalog requires: Global Search, Mega Shuffle, Vault, Smart Streams, Star Finder, managed downloads, website filters, resolver preferences, diagnostics and skin integration.

---

## After the Anniversary Year

2026 was AdultHideout's 10th anniversary year, and with Lighthouse that year comes to a close. A lot has changed since the big **1.0.0** rewrite in August 2025:

- **From fewer than 25 to more than 300 websites**, across 28 releases.
- **AdultHideout Core**, a native engine for Windows, macOS, Android and Linux that handles page fetches, Global Search and stream relaying.
- **Global Search, Mega Shuffle, Vault, Smart Streams, Star Finder** and managed downloads, built on top of the 1.0.0 foundation.
- **AdultHideout Diagnostics**, which tests every single website before a release.

To mark the end of the anniversary year, AdultHideout gets a new fanart: the AdultHideout club, now without the anniversary cake, as a lasting home for everything that comes next.

---

## Current Release: AdultHideout 1.0.28 "Lighthouse"

**Released November 18, 2026**

Lighthouse brings 14 new websites, length and quality filters for Global Search, a renewed AdultHideout Core 1.0.3 that searches 281 sources natively, page fetches through the Core and a diagnostics checklist that tested every single website and led to repairs on 21 of them.

### 14 New Websites

Anybunny, CamHub, CamWhoresBay, Erogarga, Extreme.Adult, FullTaboo, Incesto69, PervTube, PlayVids, TabooDude, TabooJizz, TabooTube, WatchPornX and WildKittys.

### Global Search

- **Length & Quality Filters:** Two new entries in the Global Search menu. Length: any, 10+, 20+, 40+ minutes or full movie. Quality: any, 720p and better, 1080p and better, 4K only.
- **Filters at the Source:** eporner, SpankBang, XNXX, xHamster and TubePornClassic filter on their own side, so every page holds only matching videos; the Core drops videos that are too short while it parses.
- **Word Matching:** Multi-word queries match by words in any order ("asmr hospital" finds "Hospital ASMR ...").
- **One Pass, Every Source:** All 300+ websites are queried by AdultHideout Core in a single concurrent request, with the website modules taking over wherever a site needs its dedicated logic.
- **Cleaner Results:** Ads, redirect links, category, tag and listing pages are filtered out automatically.

### AdultHideout Core 1.0.3

- **Site Profiles:** The Core runs AdultHideout's own search patterns for 57 more websites, so 281 sources now search natively, with at least 90% of the results of the dedicated module and about three times faster per site.
- **Failure Reasons:** The Core reports why a website failed (offline, not found, rate limited, Cloudflare), and Global Search skips retries that cannot succeed.
- **Honest Challenge Status:** An unsolved Cloudflare challenge is reported as an error instead of a success.
- **Page Fetches through the Core:** Website pages, including modules built on urllib, are fetched through the Core, while video, HLS and thumbnail transfers stay direct.
- **Local HLS & MP4 Stream Relay:** Adaptive HLS playlists auto-select 1080p variants, and HTTP 206 byte-range seeking keeps MP4 playback smooth.
- **Embedded QuickJS Runtime:** Packed player scripts and signed stream tickets are evaluated in milliseconds.
- **On-Demand Platform Binary Delivery:** The Core Service detects the device and downloads only the matching binary, replacing older Core versions automatically on the next start:
  - **Windows**: 64-bit Desktop (`windows-x86_64`)
  - **macOS**: Apple Silicon (`darwin-arm64`) & Intel (`darwin-x86_64`)
  - **Android / Google TV / Fire TV**: 64-bit (`android-arm64-v8a`) & 32-bit (`android-armeabi-v7a`)
  - **Linux / LibreELEC / CoreELEC / Raspberry Pi**: `linux-x86_64`, `linux-aarch64` & `linux-armv7`

### Playback & Stability

- **No More Stalls:** A failed resolve ends cleanly, and playlists no longer press Next while a video is still resolving.
- **Leaner Data:** Global Search results are stored per search instead of in the shared state file.
- **Official Source Check:** Warns again when AdultHideout was installed from an unofficial source.

### Diagnostics 0.3.0

Every website is checked for a reachable domain, an English start page, its buttons, listed videos, real thumbnails, a playable 5th video and Core use, 16 websites at a time.

### Website Repairs & Cleanup

- **Repaired:** 3Movs, Balbums, BornToBeFuck, Fuqster, HentaiMama, HQPorner, JavHDPorn, JustFullPorn, LetMeJerk, PornAVHD, PornDoe, Pornhub, SexTB, Taxi69, Upornia, VintagePornFun, WOW.xxx, XHamster, XNXX, XTapes and YouJizz, plus the LuLuStream resolver.
- **Removed:** PornRabbit (the tube is closed) and SaintPorn (the domain redirects to a paywall).
- **Hidden by default:** MyClassicP and VintageWorldP now put an interactive Cloudflare challenge in front of every page; they can be shown again under Settings > Website options > Manage hidden websites.

Full notes: [Lighthouse 1.0.28](docs/releases/1.0.28-lighthouse.md) · [changelog.txt](plugin.video.adulthideout/changelog.txt)

---

## What AdultHideout Can Do

- Browse **300+ supported websites** through one consistent Kodi interface.
- Search across selected sources—or all 300+ sites at once—with **Global Search** and **Mega Shuffle**.
- Save videos to **Vault**, organize collections, rate entries and build a personal Vault TV channel.
- Download supported streams through the managed **Download Center** to local, SMB or NFS storage.
- Play completed downloads through **Offline videos**.
- Sort and filter the website catalog by name, age and content category.
- Choose preferred resolvers and skip mirrors that do not work well on a device.
- Create optional website collections for custom Kodi home screens and compatible skins.
- Run privacy-safe tests with the optional **AdultHideout Diagnostics** companion.
- Explore performers and known full-length titles through **Star Finder (Beta)**.
- Build continuously refilled personal channels with **Smart Streams (Beta)**.

## Supported Platforms

AdultHideout targets **Kodi 19 or newer** and uses Kodi's Python 3 runtime alongside the native **AdultHideout Core** engine:

- **Windows** (`x86_64`)
- **macOS** (Apple Silicon `M1/M2/M3/M4` & Intel `x86_64`)
- **Android, Google TV & Amazon Fire TV** (`arm64-v8a` & `armeabi-v7a`)
- **Linux, LibreELEC, CoreELEC & Raspberry Pi** (`x86_64`, `aarch64` & `armv7`)

Individual websites can behave differently across platforms because their servers, CDNs and delivery systems change independently of AdultHideout. Diagnostics can test the addon directly on the affected device.

## Languages

The AdultHideout interface, including the Global Search presets, Mega Shuffle controls and setup dialogs, is fully localized in:

- English (`en_GB`)
- German (`de_DE`)
- French (`fr_FR`)
- Spanish (`es_ES`)
- Italian (`it_IT`)

Website titles and metadata remain in the language supplied by each source.

## Installation

Install the **AdultHideout Repository** first so Kodi can receive AdultHideout, the Core service, and future updates automatically.

- **Kodi File Manager (recommended):** Add `https://vashiel.github.io/repository.adulthideout/` as a source, install `repository.adulthideout-1.0.5.zip`, then install AdultHideout from the new repository.
- **Direct ZIP:** Download [repository.adulthideout-1.0.5.zip](https://github.com/Vashiel/repository.adulthideout/raw/master/repository.adulthideout-1.0.5.zip), open **Add-ons → Install from zip file**, and select it.
- **Fire TV / Android TV:** Open Downloader and enter shortcode **`9480267`** (or `aftv.news/9480267`), then install the downloaded repository ZIP in Kodi.

Kodi may require **Unknown sources** to be enabled before installing the repository. The illustrated steps, update instructions and troubleshooting are available in the **[complete Installation guide](https://github.com/Vashiel/repository.adulthideout/wiki/Installation)**.

After adding the repository, install **AdultHideout** from **Video add-ons**. Kodi automatically includes **AdultHideout Core Service**, which downloads the small (~3 MB) native engine matched to your device and starts it instantly. The optional **AdultHideout Diagnostics** companion is available under **Program add-ons**.

## Help And Documentation

The official **[AdultHideout Wiki](https://github.com/Vashiel/repository.adulthideout/wiki)** is the user handbook for installation, website discovery, Global Search, Vault, downloads, Diagnostics, issue reports and optional skin integration.

- **Homepage:** [vashiel.github.io/repository.adulthideout](https://vashiel.github.io/repository.adulthideout/)
- **Wiki:** [Features, guides and support](https://github.com/Vashiel/repository.adulthideout/wiki)
- **Issues:** [Bug reports and feature requests](https://github.com/Vashiel/repository.adulthideout/issues)
- **Discussions:** [Announcements and community discussion](https://github.com/Vashiel/repository.adulthideout/discussions)
- **Changelog:** [Complete release history](plugin.video.adulthideout/changelog.txt)
- **Release notes:** [Lighthouse 1.0.28](docs/releases/1.0.28-lighthouse.md) · [Quicksilver 1.0.27](docs/releases/1.0.27-quicksilver.md) · [Core Horizon 1.0.26](docs/releases/1.0.26-core-horizon.md) · [Prism 1.0.25](docs/releases/1.0.25-prism.md)

## Disclaimer

AdultHideout is intended for adults only. It does not host third-party videos and is not affiliated with supported websites. Content, streams and metadata are provided by their respective third-party operators.
