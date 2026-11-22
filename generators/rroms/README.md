# Reference generator: r/ROMs megathread

Builds [`dist/rroms.addon.json`](../../dist/rroms.addon.json) from the public sources of the
[r/ROMs megathread site](https://r-roms.github.io/).

```
python generators/rroms/generate.py                   # live site, no verification
python generators/rroms/generate.py --verify          # also drop collections Internet Archive removed
python generators/rroms/generate.py --source-dir DIR  # read a local copy of the site sources
```

## How it works

1. `parse.py` reads the site's navigation and every console page and extracts, for each table row, its title and all the
   `archive.org` links (links to other hosts, such as torrent sites, are ignored: the addon is Internet Archive only).
2. `classify.py` assigns each row to a canonical console id from [`spec/platforms.json`](../../spec/platforms.json).
   The site groups many consoles on one page ("Nintendo Games" holds the NES, SNES, N64 and Game Boy families), so rules
   are **per page**, the first matching rule wins, and rules look at the title and at the item identifier together. A row
   that no rule can place stops the run (exit status 2), so new rows never end up in the wrong place silently.
3. `generate.py` removes duplicates, applies the known fixes for upstream mistakes, optionally checks each item against the
   Internet Archive (`--verify`), builds the manifest in category/console order and validates it with the same validator
   used for hand-written addons.

`--verify` asks the public metadata API whether each item still exists and whether the folder or file in `source.path` is
in it. Network trouble never removes a collection: only a clear "item not found / no files" answer does.

## Tests

`python -m unittest discover -s tests` runs the parser, the classification rules and the generator against the small
copy of the site in `tests/fixtures/rroms/`.
