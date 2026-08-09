# AdultHideout Diagnostics

AdultHideout Diagnostics is the optional testing companion for AdultHideout.
It runs entirely inside Kodi and therefore checks the same network, Python,
resolver, proxy, playback and artwork environment that the user experiences.
It can be opened from AdultHideout's Diagnostics settings section, which also
offers to install the companion add-on when it is missing. The interface is
available in English, German, Spanish and Italian.

## Test modes

- **Smart check all websites** screens every listing and thumbnail first. Only
  suspicious websites enter a deeper folder check. Smart checks never start
  unknown streams automatically, because a broken decoder or network stream
  can block Kodi itself. This is the recommended default.
- **Quick listing check all websites** checks listings and the first available
  video thumbnail without starting playback.
- **Select websites** runs Smart, Quick or Full against a user-selected group.
- **Full playback check** follows useful folders and tries up to three videos,
  including startup and seek checks. It is available for selected websites.
- **Retest failed** repeats only non-passing sites from the latest report. After
  a Quick report it automatically upgrades those sites to deeper folder checks.

Tests run sequentially inside a persistent queue worker, avoiding hundreds of
short-lived Kodi Python interpreters. Every website has a fixed timeout; if one
source stalls, only that source is marked and the remaining queue continues.
Abandoned worker files are cleaned automatically on the next run.
Known external outages are recorded separately and do not enter the automatic
repair list.

Listing checks count only playable video entries, so a page containing only
Search, Categories or other menu folders cannot pass accidentally. Thumbnail
checks use Kodi's VFS first and a small direct HTTP probe only when VFS returns
an empty response; no image is cached on disk.

## Reports

Reports are stored in the add-on profile under `reports/` and can be exported
from the main menu. The JSON format includes Kodi, platform, skin and add-on
versions plus per-site timings and outcomes. Video titles, complete stream
URLs, credentials, cookies and authorization headers are not included.

The report schema distinguishes passed sites, warnings, confirmed failures,
timeouts and known external outages. Smart reports also retain the compact
screening result when a website required a deeper check.

## Platforms

The add-on uses only Python's standard library and Kodi APIs. It does not need
ADB, a Kodi web server, external Python, platform-specific binaries or the
desktop KVAT development harness.
