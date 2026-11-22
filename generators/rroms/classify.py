"""Maps rows of the r/ROMs megathread to canonical console ids (see spec/platforms.json).

Rules are scoped per page on purpose: "Nintendo 64" inside the Wii U page is a Virtual Console pack that belongs
to the Wii U, not to the Nintendo 64. The first matching rule wins, so more specific rules come first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PageRules:
    default: str | None = None
    rules: tuple[tuple[str, str], ...] = field(default_factory=tuple)


PAGES: dict[str, PageRules] = {
    "/Nintendo/nintendo-games": PageRules(
        None,
        (
            (r"Family Computer Disk System|\bFDS\b", "nintendo-fds"),
            (r"Super Nintendo|\bSNES\b", "nintendo-snes"),
            (r"Nintendo 64DD", "nintendo-64dd"),
            (r"Nintendo 64|\bN64\b", "nintendo-64"),
            (r"Nintendo Entertainment System|\bNES\b", "nintendo-nes"),
            (r"Game ?Boy Color", "nintendo-gbc"),
            (r"Game ?Boy Advance", "nintendo-gba"),
            (r"Game ?Boy", "nintendo-gb"),
            (r"Pok[eé]mon Mini", "nintendo-pokemon-mini"),
            (r"Virtual Boy", "nintendo-virtual-boy"),
        ),
    ),
    "/Nintendo/nintendo-ds": PageRules("nintendo-ds", ((r"DSi", "nintendo-dsi"),)),
    "/Nintendo/nintendo-3ds": PageRules("nintendo-3ds"),
    "/Nintendo/nintendo-gamecube": PageRules("nintendo-gamecube"),
    "/Nintendo/nintendo-wii": PageRules("nintendo-wii"),
    "/Nintendo/nintendo-wii-u": PageRules("nintendo-wii-u"),
    "/Sony/sony-playstation": PageRules("sony-ps1"),
    "/Sony/sony-playstation-2": PageRules("sony-ps2"),
    "/Sony/sony-playstation-portable": PageRules("sony-psp"),
    "/Sony/sony-playstation-3": PageRules("sony-ps3"),
    "/Sony/sony-playstation-vita": PageRules("sony-vita"),
    "/Microsoft/microsoft-xbox": PageRules("microsoft-xbox"),
    "/Microsoft/microsoft-xbox360": PageRules("microsoft-xbox360"),
    "/Sega/sega-games": PageRules(
        None,
        (
            (r"32X", "sega-32x"),
            (r"Game Gear", "sega-game-gear"),
            (r"Master System", "sega-master-system"),
            (r"Mega Drive|Genesis", "sega-mega-drive"),
        ),
    ),
    "/Sega/sega-dreamcast": PageRules("sega-dreamcast"),
    "/Sega/sega-saturn": PageRules("sega-saturn"),
    "/Sega/sega-cd": PageRules("sega-cd"),
    "/Retro & Arcade/retro-games": PageRules(
        None,
        (
            (r"Jaguar CD|jagcd", "atari-jaguar-cd"),
            (r"Jaguar", "atari-jaguar"),
            (r"Atari - 2600", "atari-2600"),
            (r"Atari - 5200", "atari-5200"),
            (r"Atari - 7800", "atari-7800"),
            (r"PC Engine CD|TurboGrafx CD|pcecd|pc-engine-cd", "nec-pc-engine-cd"),
            (r"PC Engine|TurboGrafx", "nec-pc-engine"),
            (r"PC-FX|pc_fx", "nec-pc-fx"),
            (r"PC-98", "nec-pc-98"),
            (r"Neo ?Geo CD|ngcd|snk_neo_geo", "snk-neo-geo-cd"),
            (r"3DO", "panasonic-3do"),
            (r"CD-i", "philips-cdi"),
            (r"Pippin", "bandai-pippin"),
            (r"FM[- ]Towns|fm_towns", "fujitsu-fm-towns"),
        ),
    ),
    "/Retro & Arcade/arcade": PageRules(
        None,
        (
            (r"FireBeat", "arcade-konami-firebeat"),
            (r"Konami - M2", "arcade-konami-m2"),
            (r"System 573", "arcade-konami-system-573"),
            (r"System GV", "arcade-konami-system-gv"),
            (r"e-Amusement", "arcade-konami-e-amusement"),
            (r"Triforce", "arcade-triforce"),
            (r"System 246", "arcade-namco-system-246"),
            (r"Chihiro", "arcade-sega-chihiro"),
            (r"Lindbergh", "arcade-sega-lindbergh"),
            (r"Naomi 2", "arcade-sega-naomi-2"),
            (r"Naomi", "arcade-sega-naomi"),
            (r"RingEdge 2", "arcade-sega-ringedge-2"),
            (r"RingEdge", "arcade-sega-ringedge"),
            (r"MAME", "arcade-mame"),
            (r"FinalBurn|\bFBN\b|fbneo", "arcade-fbneo"),
        ),
    ),
    "/PC/pc-games": PageRules(
        None,
        (
            (r"Total DOS|ExoDos", "pc-dos"),
            (r"eXoWin3", "pc-windows"),
            (r"DOOM", "pc-doom"),
            (r"Macintosh", "apple-macintosh"),
            (r"PC[- ]Compatible|IBM - PC", "pc-redump"),
        ),
    ),
}

# Known mistakes upstream: (title, identifier, wrong path) -> right path. They are dropped by --verify if still wrong.
PATH_FIXES: dict[tuple[str, str, str], str] = {
    ("Atari - 5200", "ni-roms", "roms/Atari - 2600.zip"): "roms/Atari - 5200.zip",
}

_COMPILED = {
    page: (rules.default, [(re.compile(pattern, re.IGNORECASE), console) for pattern, console in rules.rules])
    for page, rules in PAGES.items()
}


def classify(page: str, title: str, identifiers: list[str]) -> str | None:
    """Returns the console id for a row, or None if the page is unknown or nothing matches."""
    if page not in _COMPILED:
        return None
    default, rules = _COMPILED[page]
    # Title and identifiers are searched together: a title can be vague ("Atari Jaguar") while the identifier
    # of the item ("jagcd-chd-zstd") says what it really is. Rule order decides ties.
    haystack = f"{title} {' '.join(identifiers)}"
    for pattern, console in rules:
        if pattern.search(haystack):
            return console
    return default


# Items that hold one big zip with every game of a console: the app lists the games inside and downloads them one by one.
EXPAND_ZIP = {
    ("NES_Test_Collection_3", ""),
    ("No-Intro_SNES_Collection", ""),
    ("No-Intro_GameBoy_Collection", ""),
    ("No-Intro_GameBoy_Color_Collection", ""),
    ("No-Intro_GameBoy_Advance_Collection", ""),
    ("DS-No-Intro-2024-Myrient-Zipped", ""),
    ("DSi-No-Intro-2024-Myrient-Zipped-2", ""),
    ("ni-roms", "roms/Atari - 2600.zip"),
    ("ni-roms", "roms/Atari - 5200.zip"),
    ("ni-roms", "roms/NEC - PC Engine - TurboGrafx-16.zip"),
    ("ni-roms", "roms/Sega - 32X.zip"),
    ("ni-roms", "roms/Sega - Game Gear.zip"),
    ("ni-roms", "roms/Sega - Master System - Mark III.zip"),
    ("ni-roms", "roms/Sega - Mega Drive - Genesis.zip"),
}


def should_expand(identifier: str, path: str) -> bool:
    return (identifier, path) in EXPAND_ZIP


def fix_path(title: str, identifier: str, path: str) -> str:
    return PATH_FIXES.get((title, identifier, path), path)
