# Archive Fetcher addon specification — version 1

An **addon** tells the Archive Fetcher app *where* things are on the Internet Archive. It is a single JSON file
that contains **no code and no files**: only a catalog of Internet Archive items, grouped by manufacturer and console.

The app ships with no catalog of its own. Everything it shows comes from the addons the user installed.

- [1. Hosting and installing](#1-hosting-and-installing)
- [2. The manifest](#2-the-manifest)
- [3. Categories and consoles](#3-categories-and-consoles)
- [4. Collections and sources](#4-collections-and-sources)
- [5. How the app merges addons](#5-how-the-app-merges-addons)
- [6. Limits](#6-limits)
- [7. Versioning and compatibility](#7-versioning-and-compatibility)
- [8. Security and privacy model](#8-security-and-privacy-model)
- [9. Validating a manifest](#9-validating-a-manifest)
- [10. Changelog](#10-changelog)

The key words MUST, SHOULD and MAY are used as in RFC 2119. The Python validator in
[`tools/addonlib/validate.py`](../tools/addonlib/validate.py) is the reference implementation of the rules below.

## 1. Hosting and installing

A manifest is a UTF-8 JSON file (without a byte order mark) served over **HTTPS** (any host: GitHub raw files, GitHub Releases, GitHub Pages,
your own server). It MUST be at most **5 MiB**. The app follows redirects.

Users install an addon in the app under **Addons → Add addon** by pasting the manifest URL, or by opening a link
of the form:

```
archivefetcher://addon?url=<percent-encoded https URL of the manifest>
```

The link only pre-fills the "Add addon" screen; the user always has to confirm. Debug builds of the app also accept
`http://` URLs for `localhost`, `127.0.0.1` and `10.0.2.2` (the Android emulator's alias for the host computer),
which is how you test an addon before publishing it.

The app keeps a copy of every installed manifest, so addons keep working offline, and checks the URL again at
startup when the copy is older than 12 hours. A failed refresh never removes the stored copy.

## 2. The manifest

The top level is a JSON object:

| Field         | Type    | Required | Rules |
|---------------|---------|----------|-------|
| `spec`        | integer | yes      | Must be `1`. |
| `id`          | string  | yes      | Stable identifier of the addon, `^[a-z0-9][a-z0-9._-]{1,63}$`. Installing a manifest whose `id` is already installed replaces the old one. |
| `name`        | string  | yes      | Shown in the app, 1–60 characters. |
| `version`     | string  | yes      | Free text such as `1.0.0` or `2026.11.22`, up to 32 characters. Informational. |
| `description` | string  | no       | Up to 400 characters. |
| `homepage`    | string  | no       | An `https://` URL, up to 300 characters. |
| `categories`  | array   | yes      | At least one [category](#3-categories-and-consoles). |

Unknown fields are ignored, so addons may carry extra metadata.

## 3. Categories and consoles

The app shows a two-level tree: **categories** (usually a manufacturer: Nintendo, Sony, Sega…) containing
**consoles** (a single platform: Nintendo - Game Boy Advance). Splitting systems this way is what makes browsing and
searching targeted: the user picks a manufacturer, then a console, and only then sees games.

**Category**

| Field      | Type   | Rules |
|------------|--------|-------|
| `id`       | string | `^[a-z0-9][a-z0-9-]{0,59}$`, unique in the manifest. |
| `name`     | string | 1–60 characters. |
| `consoles` | array  | [Consoles](#3-categories-and-consoles) of this category. |

**Console**

| Field         | Type   | Rules |
|---------------|--------|-------|
| `id`          | string | `^[a-z0-9][a-z0-9-]{0,59}$`, unique in the **whole manifest** (not only inside its category). |
| `name`        | string | 1–80 characters. Use the No-Intro / Redump style, e.g. `Nintendo - Game Boy Advance`. |
| `collections` | array  | The [collections](#4-collections-and-sources) available for this console. A console without collections is not shown. |

**Use the canonical ids.** [`spec/platforms.json`](../spec/platforms.json) lists the ids of the common categories and
consoles ([human-readable version](PLATFORMS.md)). Reusing them lets the app merge your addon with others: a user with two
addons that both provide `sony-psp` sees one *Sony - PlayStation Portable* console with the collections of both.
You may use ids that are not in the list for platforms that are missing; they simply will not merge with anyone else's.

## 4. Collections and sources

A **collection** is a titled pointer to part of an Internet Archive item. In the app it becomes one entry of the
"Collection" filter, and its files are listed together with those of the other collections of the same console.

| Field    | Type   | Required | Rules |
|----------|--------|----------|-------|
| `title`  | string | yes      | 1–160 characters. Shown to the user. A collection split into volumes should say so: `… (Part 1)`. |
| `source` | object | yes      | Where the files are. See below. |
| `format` | string | no       | Lower-case file type of what the user ends up with: `iso`, `chd`, `zip`, `cso`… (`^[a-z0-9]{1,8}$`). Shown as the *Format* filter. When missing, the app looks for a `.ext` word in the title (`PSP Redump .chd`) and then uses the file extension. Set it when archives hide the real format, e.g. `.zip` files that contain ISOs. |

**Source** — only one type exists in spec version 1:

| Field  | Type   | Required | Rules |
|--------|--------|----------|-------|
| `type` | string | yes      | `"archive.org-item"`. |
| `id`   | string | yes      | The Internet Archive item identifier, i.e. the last part of `https://archive.org/details/<id>`. `^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$`. |
| `path` | string | no       | Restricts the collection to a part of the item, **relative to the item root**, without a leading `/`, without empty or `.`/`..` segments and without `\`. It can be a folder (all files below it, recursively) or a single file. A file belongs to the collection when `name == path` or `name` starts with `path + "/"`. |
| `expand` | string | no       | `"zip"`: the files selected by `path` are zip archives, and the app should list the files **stored inside them** (Internet Archive serves the contents of a zip at `https://archive.org/download/<id>/<zip path>/` and every member at `https://archive.org/download/<id>/<zip path>/<member>`), so the user can download single games instead of the whole zip. Use it for items that pack a whole console into one zip. Any other value is invalid. |

Which files the user sees is decided by the app from the item's public metadata (`https://archive.org/metadata/<id>`),
skipping Internet Archive's own metadata files, thumbnails and torrents. Items that require an Internet Archive account
are marked as locked in the app.

A collection with an **unknown `source.type`** is skipped by apps that do not know it (validators report a warning), so
future source types can be added without breaking old apps.

## 5. How the app merges addons

- Categories are merged by `id`, consoles by `id`; collections are appended.
- The `name` shown is the one from the addon installed first.
- Categories and consoles keep the order of the first addon that declared them.
- The same item can appear in several addons; the app lists each file once.

## 6. Limits

| What                                | Limit      |
|-------------------------------------|------------|
| Manifest size                       | 5 MiB      |
| Categories                          | 100        |
| Consoles (total)                    | 500        |
| Collections (total)                 | 10 000     |
| Collections per console             | 2 000      |

The app rejects a manifest that exceeds a limit and tells the user why.

## 7. Versioning and compatibility

`spec` is a single integer. A change that old apps cannot understand increments it; apps refuse manifests with a
`spec` higher than they support and show a message asking the user to update. Additive changes (new optional fields,
new source types) do not increment it.

## 8. Security and privacy model

- A manifest is **data**. The app never runs anything from it.
- Only `https://` URLs are accepted (plus the local test hosts in debug builds).
- File paths from manifests and from the Internet Archive are sanitized before anything is written to the device.
- Fetching a manifest reveals the user's IP address to the host that serves it, like any web request. Nothing else
  about the user is sent. Downloads go straight from `archive.org` to the device.
- Addon authors are responsible for what their addon points to. The app does not host, mirror or index files.

## 9. Validating a manifest

```
python tools/validate_addon.py my.addon.json
```

The tool prints every problem with its location (for example `categories[0].consoles[1].collections[3].source.id`)
and exits with status 1 when the manifest is invalid. Warnings (unknown ids, unknown source types) do not fail.
[`spec/addon.schema.json`](../spec/addon.schema.json) is a JSON Schema for editor completion; where the two disagree,
the validator wins.

## 10. Changelog

- **1** — first version: categories, consoles, collections, the `archive.org-item` source.
