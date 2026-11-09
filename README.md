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

## Current Release: AdultHideout 1.0.27 "Quicksilver"

**Released November 9, 2026**

AdultHideout 1.0.27 unlocks the full potential of **AdultHideout Core**. Global Search and Mega Shuffle now run natively in Rust from the first request to the last result: every source is queried by the Core in a single pass, with AdultHideout's website modules seamlessly covering the rest. The result is our fastest, most complete and cleanest search ever, backed by more than two dozen refreshed websites.

### Native Core Search

Quicksilver hands the entire Global Search to the native engine introduced with Core Horizon:

- **One Pass, Every Source:** All 300+ websites are queried by AdultHideout Core in a single concurrent request, with AdultHideout's website modules taking over wherever a site needs its dedicated logic.
- **Smarter Result Recognition:** The Core now understands site APIs, WordPress and RSS feeds, search forms, regional domains and Cyrillic titles, so far more sources deliver matches.
- **Cleaner Results:** Ads, redirect links, category, tag and listing pages are filtered out automatically, leaving only real videos.
- **Streamlined Network Layer:** Lean, direct requests make the Core search more than twice as fast as before.

---

### Real-World Search Benchmark (300+ Sources)

| Search Scope | AdultHideout 1.0.26 | Quicksilver (Desktop) | Quicksilver Core (Mobile / ARM64) |
| :--- | :--- | :--- | :--- |
| **All 302 Sources, "milf"** | 24 sec · 3,344 results | **18 sec · 4,018 results** | – |
| **Mega Shuffle, "sex"** | – | **~18 sec · ~3,370 results** | **~12 sec · ~3,800 results** |

> **Real-World Test**: Across **all 302 enabled websites** on a Windows desktop, Quicksilver returns **20% more results in 25% less time** than the previous release.

---

### Key Technical Subsystems in AdultHideout Core

The native Core service (`service.adulthideout.core`) runs as a local engine on `127.0.0.1:8191` (in-process via C-ABI `ctypes` on Android) and provides:

- **Concurrent Multi-Site Search Engine:** Queries every source in one pass with parallel workers, a global time budget, automatic retries and intelligent result filtering.
- **Local HLS & MP4 Stream Relay:** Rewrites adaptive HLS (`.m3u8`) playlists to auto-select 1080p Full HD variants and handles HTTP 206 byte-range seeking for smooth MP4 playback.
- **Embedded QuickJS Runtime:** Evaluates packed player scripts and signed stream ticket APIs in milliseconds.
- **On-Demand Platform Binary Delivery (~3 MB):** The Core Service add-on detects the device and downloads only the matching binary, starting it instantly with no Kodi restart:
  - **macOS**: Apple Silicon (`darwin-arm64`) & Intel (`darwin-x86_64`)
  - **Android / Google TV / Fire TV**: 64-bit (`android-arm64-v8a`) & 32-bit (`android-armeabi-v7a`)
  - **Windows**: 64-bit Desktop (`windows-x86_64`)
  - **Linux / LibreELEC / CoreELEC / Raspberry Pi**: `linux-x86_64` & `linux-aarch64`

---

### Website Refresh & Playback

- **27 Websites Refreshed:** Search and playback modernized for Aki-H, BDSMVilla, Erome, EroticMV, FapNFuck, FullPorner, Fuqster, Hanime, HDEasyPorn, HDShemalez, Heavy-R, HentaiCity, HentaiMama, Hentaisea, IcePornCasting, LeakGallery, MixPorn, PMVHaven, PornKTube, PornZog, ShowCamRips, StreamPorn, SunPorno, ThisVid, W1mp, WOW.xxx and X24Video.
- **New Embedded Player Resolver:** Native support for the txxx player network across partner sites.
- **Direct CDN Streaming:** Signed CDN delivery for KVS-powered websites.
- **Universal Stream Headers:** Stream headers are encoded so every player and device reads them correctly.

For detailed scraper repairs and full commit history, consult [changelog.txt](plugin.video.adulthideout/changelog.txt) and the [Quicksilver Release Notes](docs/releases/1.0.27-quicksilver.md).

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
- **Linux, LibreELEC, CoreELEC & Raspberry Pi** (`x86_64` & `aarch64`)

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
- **Release notes:** [Quicksilver 1.0.27](docs/releases/1.0.27-quicksilver.md) · [Core Horizon 1.0.26](docs/releases/1.0.26-core-horizon.md) · [Prism 1.0.25](docs/releases/1.0.25-prism.md)

## Disclaimer

AdultHideout is intended for adults only. It does not host third-party videos and is not affiliated with supported websites. Content, streams and metadata are provided by their respective third-party operators.
