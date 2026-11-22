# Cartshelf addons

Addons for **Cartshelf**, an Android app that browses and downloads game files, console by console, from the
Internet Archive and other public websites.
The app contains no catalog of its own: *addons* tell it which Internet Archive collections exist and which console
each one belongs to. This repository holds

- the **addon specification** and the **guide for writing your own addon** — [`docs/`](docs/)
- a **validator** for manifests — [`tools/validate_addon.py`](tools/validate_addon.py)
- the **reference addon**, a catalog of the collections listed by the r/ROMs megathread, grouped by manufacturer and
  console, together with the script that generates it — [`generators/rroms/`](generators/rroms/) and
  [`dist/rroms.addon.json`](dist/rroms.addon.json)

An addon is one JSON file with no code and no files in it, only Internet Archive item identifiers.

## Install the reference addon

Download `rroms.addon.json` from the [latest release](https://github.com/DanieleKun/Addon-Archive-Fetcher/releases/latest)
and, in the app, open **Addons → Add from file**.

When the repository is public, the app can also add it by address, which keeps it updated automatically
(the app refreshes it at startup when its copy is older than 12 hours). Paste under **Addons → Add addon**:

```
https://github.com/DanieleKun/Addon-Archive-Fetcher/releases/latest/download/rroms.addon.json
```

While the repository is private, that link only works in a browser signed in to GitHub, so use *Add from file*.

## What the reference addon looks like

```
Nintendo      NES · SNES · Nintendo 64 · Game Boy · Game Boy Color · Game Boy Advance ·
              DS · DSi · 3DS · GameCube · Wii · Wii U
Sony          PlayStation · PS2 · PSP · PS3 · Vita
Microsoft     Xbox · Xbox 360
Sega          Master System · Mega Drive · 32X · Game Gear · Mega CD · Saturn · Dreamcast
Atari · NEC · SNK · Other consoles · Arcade · Computers
```

The full tree with the console ids is in [`docs/PLATFORMS.md`](docs/PLATFORMS.md).

## Write your own addon

Read [`docs/CREATING-ADDONS.md`](docs/CREATING-ADDONS.md), then check your file with

```
python tools/validate_addon.py my.addon.json
```

The exact format is in [`docs/SPEC.md`](docs/SPEC.md).

## Development

```
python -m unittest discover -s tests          # run the tests
python generators/rroms/generate.py --verify  # rebuild dist/rroms.addon.json
python tools/gen_platforms_doc.py             # after editing spec/platforms.json
```

Python 3.10 or newer, standard library only. [`CONTRIBUTING.md`](CONTRIBUTING.md) explains how to propose changes.
GitHub Actions validate every change, refresh the reference catalog every week and attach it to releases
(`.github/workflows/`).

## Legal

This project hosts no files and its addons cannot contain any: they list identifiers of items that the Internet Archive
publishes. Everyone who writes or installs an addon is responsible for what it points to; please respect the Internet
Archive's terms of use and any takedown it applies. The reference catalog is derived from the public
[r/ROMs megathread](https://r-roms.github.io/) (GPL-3.0); this repository is released under the GPL-3.0 as well
([`LICENSE`](LICENSE)).
