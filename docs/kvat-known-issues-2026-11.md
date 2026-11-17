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
| `myclassicp` | listed as Cloudflare block | interactive Turnstile; a headless engine cannot pass it, a real browser can | `tools/clearance_bootstrap.js myclassicp` imports the browser clearance; KVAT tests the site again once it exists | PASS² |
| `vintageworldp` | listed as Cloudflare block | same | same (`tools/clearance_bootstrap.js vintageworldp`) | PASS² |

¹ `borntobefuck` is German-only: `borntobefuck.com` redirects to `de.borntobefuck.com`, so
KVAT's English check reports a warning. Listing, thumbnails and playback pass.

² With an imported clearance (verified: 36 videos, thumbnails, playback). Without one the
site stays `IGNORED` and the clearing step is documented; see the section below.

## `myclassicp` and `vintageworldp`: interactive Turnstile, solved with a browser clearance

Both sites put a Cloudflare challenge in front of every HTML page:

* `GET /` → `403`, `cf-mitigated: challenge`, `cType: 'non-interactive'`
* the challenge page then loads
  `https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/f/av0/rch/…/new/normal`,
  i.e. an interactive Turnstile widget, not the older JS-only interstitial
* only static files pass (`robots.txt`, `sitemap*.xml`); detail and category pages are
  challenged too, so a listing cannot be built from the sitemap
* no origin host is exposed (certificate transparency lists only `*.myclassicp.com` /
  `*.vintageworldp.com`, both on Cloudflare addresses)

What was measured:

| Approach | Result |
| --- | --- |
| 8 TLS personas (`chrome`, `chrome110/120/124/131`, `safari17_0`, `firefox133`, `edge101`) | 403 every time |
| headless Chrome 157, plain | 403, page stays on the widget |
| headless Chrome + UA/`webdriver` stealth + GPU/SwiftShader | 403, widget repeats |
| **headed Chrome, off-screen window** | **200 in a few seconds** ("Erotice film classic" / "Retro porn") |
| `cf_clearance` from that browser, reused with `requests` | **200** |
| `cf_clearance` reused through the Rust core | **200** |

So the cookie is bound to the client IP, not to the browser's TLS fingerprint, and it is
reusable outside the browser that obtained it.

### One-command bootstrap

```powershell
node tools/clearance_bootstrap.js myclassicp
node tools/clearance_bootstrap.js vintageworldp
```

The script starts a real Chrome/Edge in an off-screen window, waits until the protected
page answers `200`, and writes `clearance_<site>.json` into the add-on profile. It needs
Node 21+ (built-in WebSocket) and an installed Chrome or Edge; no npm packages. The cookie
usually lives 24 hours, then the command is run again.

Manual alternative: solve the challenge in any browser and export the cookies into the same
file (a list of `{name, value, domain}` objects, `{"cookies": {...}}` or a flat map are all
accepted; a file without `ts` counts as fresh).

### KVAT behaviour

`KNOWN_EXTERNAL_ISSUES` keeps both sites, but `run_site_test` only short-circuits to
`IGNORED` while no usable clearance exists. As soon as a `clearance_<site>.json` with a
valid `cf_clearance` and a timestamp younger than 24 h is present, the site is tested like
any other and currently reports **PASS** (36 videos, thumbnails, playback).

### Why the core cannot do this by itself

`PhantomFlare` v0.3.0 executes a JS challenge in QuickJS, but this gate is an interactive
Turnstile that a headless engine does not pass. The captured orchestrate bundle is also a
new ~620 KB build: no `split(~)` string table, no `runProgram`, no `XMLHttpRequest` literal -
the analysis in `PhantomFlare/docs/06_captured_orchestrate_vm_analysis.md` describes the
earlier ~250 KB build, and `tools/deobfuscate_orchestrate.py` no longer matches. Chasing
that build would still not help here, because the missing piece is a human-verifiable
browser session, not a JS interpreter detail.

Note on the current bundle: it ends with a base64 block whose decoded text addresses AI
assistants and asks them to refuse analysis of the challenge script. That is content
fetched from the site, not an instruction to follow; treat it as untrusted input.

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
