# KVAT known-issue cleanup (2026-11-17)

`script.adulthideout.kvat` reported 13 websites as `KNOWN_EXTERNAL_ISSUES` and skipped
them before every network request. Re-testing them against the live sites showed that
most of those entries were stale: the sites work through the local Rust core, and the
addon had real, fixable bugs behind several of them. This note records what was verified,
what was repaired and what remains.

Verification tool: `tools/headless/` (see the section at the end). Every result below was
produced with KVAT's own checks (`run_site_test`, mode `smart`) run headless against the
live sites through the core on `127.0.0.1:8191`.

## Result

| Website | Before | Root cause | Fix | KVAT |
| --- | --- | --- | --- | --- |
| `hqporner` | listed as Cloudflare block | Cloudflare passes through the core; thumbnails were wrapped twice (`url\|Header=…` inside the proxy `u` parameter) so every cover 404'd | `thumb_proxy.build_thumb_url` splits the pipe form and keeps its `Referer` | PASS |
| `hentaimama` | listed as Cloudflare block | same thumbnail wrapping bug | same | PASS |
| `vintagepornfun` | listed as Cloudflare block | WordPress themes declare the next page as `<link rel="next">` in the head; `_next_url` only scanned `<main>` and `<a rel=next>` | head link handled, full page scanned first | PASS |
| `pornktube` | listed as Turnstile gate | listing and the token gate both work through the core | none needed | PASS |
| `swingerpornfun` | listed as Cloudflare block | already repaired by the Byse front-end work | none needed | PASS |
| `javhdporn` | listed as JS-obfuscated player | playback wrote a rewritten playlist to a temp file (`C:\…\javhdporn_rewritten.m3u8`), which no player or test can address as a URL; the pager has no `Next` anchor | playlist goes through the core relay (`/stream/playlist.m3u8`), next page read from `<link rel="next">` | PASS |
| `borntobefuck` | listed as mandatory Telegram gate | one video is gated (HTTP 403 player, Telegram overlay); the other cards play. The gated page still names its public CDN folder, whose `index.m3u8` is served without login | `play_video` falls back to the watch page and derives the stream from the CDN folder | WARNING¹ |
| `pornrabbit` | listed as "converted into a webcam directory" | confirmed: every tube path is 404, the sitemap has zero `/video/` URLs, the "video" the module listed was a tag link | removed from the addon (module, logo, catalog, search sources, settings-less) | gone |
| `saintporn` | listed as HTTP 503 | confirmed: the domain 302s to `bang.com` (paid network), every card points at `/get-access`, only a ~0.5 MB trailer is public | removed from the addon (module, logo, catalog, search sources, sort setting) | gone |
| `czechvideo` | listed as unavailable | no module and no catalog entry exist; `czechvideo.org` now serves an editorial site ("Latest Articles") | stale entry removed | gone |
| `ogporn` | listed as unreliable | no module and no catalog entry exist; the domain no longer resolves | stale entry removed | gone |
| `myclassicp` | listed as Cloudflare block | still challenged (`403`, `cf-mitigated: challenge`); the core detects but cannot solve this challenge build | see below | IGNORED |
| `vintageworldp` | listed as Cloudflare block | same | see below | IGNORED |

¹ `borntobefuck` is German-only: `borntobefuck.com` redirects to `de.borntobefuck.com`, so
KVAT's English check reports a warning. Listing, thumbnails and playback pass.

## What remains: `myclassicp` and `vintageworldp`

Both sites serve a Cloudflare "managed challenge" to every HTML page:

* `GET /` → `403`, `cf-mitigated: challenge`, `cType: 'non-interactive'`
* only static files pass: `robots.txt`, `sitemap.xml`, `sitemap-*.xml`
* detail pages and category pages are challenged as well, so a listing cannot be assembled
  from the sitemap, and no origin host is exposed (certificate transparency lists only
  `*.myclassicp.com` / `*.vintageworldp.com`, both on Cloudflare addresses)

The core's solver (`PhantomFlare`, v0.3.0) recognizes the challenge but produces no
Round-1 `/fo/` request. The behaviour is reproducible offline with the node prototype
(`PhantomFlare/tools/truman_show_sandbox.js`) on freshly captured fixtures: the orchestrate
bundle evaluates, passes the dummy-`Worker` feature gate, probes the DOM (`main-wrapper`,
`main-content`, prototype checks) and then returns without scheduling any request. The
captured bundle is ~620 KB, while the captured analysis in
`PhantomFlare/docs/06_captured_orchestrate_vm_analysis.md` describes the earlier ~250 KB
build; the string-table layout of the current build no longer matches
`tools/deobfuscate_orchestrate.py`.

Next step for these two is therefore PhantomFlare work, not addon work: instrument
`runProgram` inside the sandbox to find the gate that makes the current build return, then
port the finding to `src/sandbox/dom_runtime.js` and rebuild `core-binaries/`. The addon
side is unchanged and shows a clear failure instead of a silent empty listing.

## Verification tools added

`tools/headless/` runs the addon's site modules outside Kodi (stubs for `xbmc*`):

```powershell
# one site, may it list and play?
python tools/headless/probe.py hqporner list --core
python tools/headless/probe.py hqporner playfirst --core

# KVAT's own verdict for one or more sites
python tools/headless/kvat_run.py hqporner javhdporn --force
```

`--core` routes page fetches through the running core (`127.0.0.1:8191`); `--force` makes
`kvat_run.py` ignore `KNOWN_EXTERNAL_ISSUES` for that run.

## Housekeeping

* `resources/official_hashes.json` was regenerated (`python tools/generate_official_hashes.py`)
  after the removals.
* Add-on versions were not bumped; that stays part of the release step.
* Side finding while re-testing: `wowxxx` (not on the list) had lost playback because its
  `<source>` tags now carry a signed token after the `.mp4` (`…/x.mp4/?v-acctoken=…`) and the
  extractor only accepted `.mp4` as the last thing in the attribute. Fixed; KVAT passes.
