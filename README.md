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

## Current Release: AdultHideout 1.0.28 "Lighthouse"

**Released November 17, 2026**

Lighthouse brings 14 new websites, length and quality filters for Global Search, page fetches through AdultHideout Core and a diagnostics checklist that tested every website.

- **14 new websites:** Anybunny, CamHub, CamWhoresBay, Erogarga, Extreme.Adult, FullTaboo, Incesto69, PervTube, PlayVids, TabooDude, TabooJizz, TabooTube, WatchPornX and WildKittys.
- **Global Search filters:** length (up to full movie) and quality (up to 4K only) as menu entries; five big sites filter on their own side.
- **281 sources searched in the Core**, multi-word queries matched by words.
- **More stable playback:** failed resolves end cleanly, playlists no longer pile up resolves.
- **21 websites repaired**, PornRabbit and SaintPorn removed.

Full notes: [Lighthouse 1.0.28](docs/releases/1.0.28-lighthouse.md)

---

## Previous Release: AdultHideout 1.0.27 "Quicksilver"

**Released November 9, 2026**

Global Search and Mega Shuffle run natively in AdultHideout Core: all 300+ sources in a single pass, 20% more results in 25% less time. Full notes: [Quicksilver 1.0.27](docs/releases/1.0.27-quicksilver.md)

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
- **Release notes:** [Lighthouse 1.0.28](docs/releases/1.0.28-lighthouse.md) · [Quicksilver 1.0.27](docs/releases/1.0.27-quicksilver.md) · [Core Horizon 1.0.26](docs/releases/1.0.26-core-horizon.md) · [Prism 1.0.25](docs/releases/1.0.25-prism.md)

## Disclaimer

AdultHideout is intended for adults only. It does not host third-party videos and is not affiliated with supported websites. Content, streams and metadata are provided by their respective third-party operators.
