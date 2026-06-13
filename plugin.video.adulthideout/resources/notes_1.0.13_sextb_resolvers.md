# 1.0.13 Sextb Resolver Work

Sextb videos currently fall into two groups:

- Some entries show `We are updating the link for this movie, please come back later!`.
  These pages have no public server buttons and should not be treated as playable.
- Playable entries expose server buttons through `/ajax/player`.

Known server mapping from Sextb:

- `ST` -> `streamtape.net` -> supported by `streamtape_resolver.py`
- `DD` -> `dsvplay.com` / `playmogo.com` -> supported by `doodstream_resolver.py`
- `TB` -> `turboplayers.xyz` -> supported by `turboplayers_resolver.py`
- `FL` -> `ryderjet.com` -> redirects into `callistanise.com`, supported by `vidhide_resolver.py`
- `SW` -> `hglink.to` -> pending, obfuscated JavaScript shell
- `US` -> `player.upn.one` -> pending, encrypted API player
- `PP` -> `stb.strp2p.com` -> pending, encrypted API player

Known playable test pages:

- `https://sextb.net/ssni-828`
- `https://sextb.net/ssni-592`
- `https://sextb.net/ssni-965`

Known non-playable/updating examples:

- `https://sextb.net/enki-023-rm`
- `https://sextb.net/enki-024-rm`
- `https://sextb.net/enki-027-rm`

