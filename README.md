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

Global Search and Mega Shuffle now run through AdultHideout Core first: all sources go to the Core in one request, and the Python modules only search the sources the Core cannot handle or that fail in the Core. With all 302 sources this takes about 18 seconds on desktop and returns more results than the Python search alone.

- **Smarter Core search:** site APIs, feeds and POST search forms, moved domains, Cyrillic titles, and no more ads, category or tag pages among the results.
- **Content filters preserved:** sources whose modules filter blocked terms, ratings or orientation keep searching through their own module, and Core results are checked against the same blocked terms.
- **Automatic Core updates:** Core Service 1.0.1 replaces outdated Core binaries on the next start; Core 1.0.1 is built for all seven platforms.
- **27 websites repaired**, among them Aki-H, Hanime, HentaiMama, HentaiCity, LeakGallery, MixPorn, PornZog, StreamPorn, SunPorno, ThisVid and WOW.xxx.

Full notes: [Quicksilver 1.0.27](docs/releases/1.0.27-quicksilver.md)

---

## Previous Release: AdultHideout 1.0.26 "Core Horizon"

**Released November 3, 2026**

AdultHideout 1.0.26 represents a major architectural milestone: transitioning high-concurrency network tasks, stream proxying, and multi-source search operations from Kodi's Python runtime to a dedicated, native **Rust Core (`service.adulthideout.core`)**.

### Background: Why Native Rust?

For over a decade, AdultHideout operated strictly within Kodi's single-process Python 3 environment. While this worked well for single-site browsing, the requirements of modern web sources have outgrown Python's Global Interpreter Lock (GIL):
- **High-Concurrency Search**: Querying **300+ websites simultaneously** in pure Python creates significant thread contention and UI latency, especially on low-power ARM devices (Android TV, Fire TV, Raspberry Pi).
- **Stream Processing & Seeking**: Modern video platforms increasingly use fragmented MP4s, adaptive HLS manifests (`.m3u8`), and custom header requirements that Kodi's internal player cannot always resolve directly without a local proxy.
- **Dynamic JavaScript Evaluation**: Numerous platforms protect video playback tokens or embed configurations behind packed JavaScript, requiring runtime evaluation that is slow and fragile with basic regex parsers.

By offloading these workloads to a lightweight, compiled Rust engine running locally on `127.0.0.1:8191`, Kodi's Python interface remains completely responsive.

---

### Dual-Engine Hybrid Architecture

To guarantee 100% backward compatibility across all Kodi platforms, 1.0.26 operates on a dual-engine architecture:

1. **Primary Engine — AdultHideout Core (Native Rust):**
   Handles concurrent multi-site search, local HLS/MP4 stream relaying, JavaScript player unpacking, TLS session pooling, and image proxying.
2. **Classic Engine — Automatic Python Fallback:**
   If the native Core binary is not installed, declined by the user, or unsupported on a given platform, AdultHideout **automatically falls back to the classic Python engine** (the established codebase of v1.0.25). Playback and browsing continue normally with zero disruption.

---

### Real-World Search Benchmark (300+ Sources)

With search operations dispatched via asynchronous Tokio tasks in native Rust, Global Search and Mega Shuffle no longer need arbitrary timeouts or source cutoffs:

| Search Scope | Classic Python (Sequential) | Core Horizon (Mobile / ARM64) | Core Horizon (Desktop / Fast Network) |
| :--- | :--- | :--- | :--- |
| **Top Sites Preset (10–12 Sources)** | ~18 – 35 sec | **~2.5 – 4.5 sec** | **~1.2 – 2.5 sec** |
| **Mega Shuffle (All 302 Sources)** | ~15 – 25 min *(impractical)* | **~56 sec** *(~0.18s avg/site · 320+ results)* | **~12 – 18 sec** *(320+ results)* |
| **Directory Back-Navigation** | ~4 – 60 sec *(re-fetched)* | **0.001 sec** *(local page cache)* | **0.001 sec** *(local page cache)* |

> **Real-World Test**: In real-world testing across **all 302 enabled websites** on a mobile ARM64 device, a complete multi-source query finished in **56.3 seconds** (~0.18s average per site), returning **327 verified, playable results**.

---

### Key Technical Subsystems in AdultHideout Core

The native Core service (`service.adulthideout.core`) runs as an independent local background daemon (or in-process via C-ABI `ctypes` on Android) and provides several key subsystems:

- **Asynchronous Multi-Site Search Engine**: Powered by the Tokio async runtime, executing up to 48 concurrent worker pipelines with strict title relevance scoring and duration filtering.
- **Local HLS & MP4 Stream Relay (`127.0.0.1:8191`)**: A lightweight HTTP streaming relay that rewrites adaptive HLS (`.m3u8`) playlists to auto-select 1080p Full HD variants, normalizes non-standard transport stream headers (e.g. sync-byte restoration), and handles HTTP 206 byte-range seeking for smooth MP4 playback.
- **Embedded QuickJS Runtime**: Integrates a lightweight QuickJS JavaScript engine with a virtual DOM environment to evaluate packed player scripts and dynamic stream ticket APIs in under 5 milliseconds.
- **TLS Connection & Session Pooling**: Reuses persistent HTTP/2 and TLS connections across scraping requests, eliminating repetitive SSL handshakes and reducing network overhead.
- **Encrypted DNS Resolution (DoH)**: Built-in DNS-over-HTTPS fallback (Cloudflare `1.1.1.1` and Google `8.8.8.8`) ensures reliable domain resolution when local ISP or router DNS queries fail or time out.
- **On-Demand Platform Binary Delivery (~3 MB)**: To avoid distributing ~30 MB of pre-bundled binaries for architectures the user doesn't need, the core service addon is distributed at just **26 KB**. On first launch, it detects the device architecture, prompts for confirmation, downloads only the matching ~3 MB binary, and starts the service live—**no Kodi restart required**:
  - **macOS**: Apple Silicon (`darwin-arm64`) & Intel (`darwin-x86_64`)
  - **Android / Google TV / Fire TV**: 64-bit (`android-arm64-v8a`) & 32-bit (`android-armeabi-v7a`)
  - **Windows**: 64-bit Desktop (`windows-x86_64`)
  - **Linux / LibreELEC / CoreELEC / Raspberry Pi**: `linux-x86_64` & `linux-aarch64`

---

### Public Architecture Preview

Deploying native binaries across seven diverse OS and architecture targets is a significant structural evolution. AdultHideout 1.0.26 is designated as a **Public Architecture Preview**:
- Supported systems immediately receive the performance benefits of native concurrency and local stream relaying.
- The automatic Python fallback ensures uninterrupted operation on devices where native compilation or binary execution is restricted.
- Telemetry, user issue reports, and diagnostic feedback from this preview will directly inform optimizations in the 1.0.27 cycle.

For detailed scraper repairs, catalog updates, and full commit history, consult [changelog.txt](plugin.video.adulthideout/changelog.txt) and the [Core Horizon Release Notes](docs/releases/1.0.26-core-horizon.md).

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

The AdultHideout interface—including all new Core Horizon search presets, Mega Shuffle controls, and setup dialogs—is fully localized in:

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

After adding the repository, install **AdultHideout** from **Video add-ons**. Kodi will automatically include **AdultHideout Core Service**, which will prompt once to download the small (~3 MB) native engine matched to your device. The optional **AdultHideout Diagnostics** companion is available under **Program add-ons**.

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
