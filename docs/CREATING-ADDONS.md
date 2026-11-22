# Creating an addon

This guide takes you from nothing to an addon that users can install in Archive Fetcher. You need a text editor and
Python 3.10+ (only for the validator). The exact format is in the [specification](SPEC.md).

## 1. What an addon is

A single JSON file listing Internet Archive items, grouped like this:

```
Category (Nintendo)
└── Console (Nintendo - Game Boy Advance)
    └── Collection ("My GBA collection" → an Internet Archive item, or a folder/file inside it)
```

No code, no files. The app reads the file, shows the categories and consoles, and when the user opens a console it asks
the Internet Archive which files the collections contain.

## 2. Start from an example

Copy [`examples/minimal.addon.json`](../examples/minimal.addon.json) (one console, one collection) or
[`examples/multi-console.addon.json`](../examples/multi-console.addon.json) (folders, single files, formats).

Change at least `id` (unique, lower case, no spaces), `name` and `version`.

## 3. Find the Internet Archive identifiers

1. Open the item on archive.org. The address looks like `https://archive.org/details/<identifier>`. The part after
   `/details/` is the **identifier** (`source.id`).
2. If you only want part of a big item, open the item and click *Show all files*. Folders appear in the file links:
   `https://archive.org/download/<identifier>/<folder>/<file>`. Everything after the identifier is `source.path`
   (spaces and symbols can be written as they are, without `%20`).
   - a **folder** path includes every file below it;
   - a path to a **single file** makes a collection with that one file;
   - if that file (or the item's only file) is a big `.zip` holding a whole console, add `"expand": "zip"` to the source: the app then lists the games **inside** the zip and downloads only the ones the user picks.
3. Open `https://archive.org/metadata/<identifier>` in a browser if you want to check what the app will see; the
   `files` list shows every file name.

Some items need an Internet Archive account to download (the app tells the user and lets them log in). Items that were
removed from the Internet Archive cannot be loaded at all — check them before you publish.

## 4. Choose the console

Each collection goes under the console it belongs to. Use the ids from [PLATFORMS.md](PLATFORMS.md) (for example
`nintendo-gba`, `sony-psp`) and put the console under the matching category (`nintendo`, `sony`). When you reuse these ids
your addon merges with other addons: all PSP collections end up under one *Sony - PlayStation Portable*.

If a platform is not in the list, make up an id (`^[a-z0-9][a-z0-9-]{0,59}$`, unique in your file). It works fine; it
just does not merge with other addons. Open a pull request on this repository to get it added to the canonical list.

## 5. Write good collections

- **Title**: what the user should see in the filter. Say what is inside, and the format when the item mixes several:
  `PS1 Redump .chd (Part 2)`.
- **Format**: add `"format": "chd"` (or `iso`, `zip`…) when the files are archives and the real format is something
  else, or when the title cannot say it. It becomes the *Format* filter.
- **One collection per item or folder.** Do not split an item into hundreds of one-file collections; the app is made to
  load a whole collection at once and filter inside it.
- **Keep ids stable.** Changing `id` makes the app treat your addon as a new one.

## 6. Validate

```
python tools/validate_addon.py my.addon.json
```

Fix every `error`. Read the `warning`s: an id that is not in the canonical list is fine if intended.

## 7. Test it in the app

**On a phone or handheld:** publish the file (step 8) and paste its URL under *Addons → Add addon*, or copy the file
to the device and use *Addons → Add from file* (an addon added from a file is not refreshed automatically).
A link of the form `archivefetcher://addon?url=<URL-encoded address>` opens the app with the address already filled
in; the user still confirms it.

**On your computer, before publishing** (debug builds of the app, including the Android emulator):

```
cd folder-with-your-manifest
python -m http.server 8765
```

then add `http://10.0.2.2:8765/my.addon.json` in the emulator, or
`http://127.0.0.1:8765/my.addon.json` on a device connected with `adb reverse tcp:8765 tcp:8765`.
Release builds of the app only accept `https://` URLs.

Check that your categories and consoles appear, that opening a console loads the collections, and that the
filters list the regions, languages and formats you expect.

## 8. Publish on GitHub

The simplest way to host a manifest:

1. Create a public repository and commit the file.
2. Open the file on GitHub, click **Raw**, and copy the address
   (`https://raw.githubusercontent.com/<you>/<repo>/main/my.addon.json`). That is the URL users paste into the app.
3. To change the addon, edit the file and push. Users get the new version at their next app start (within 12 hours).

For releases with a stable link, attach the file to a GitHub Release; the address
`https://github.com/<you>/<repo>/releases/latest/download/my.addon.json` always points to the newest one.

The repository's `.github/workflows/validate.yml` shows how to run the validator on every push.

## 9. Generating an addon with a script

For large catalogs, write a script that produces the JSON instead of editing it by hand. The reference example is
[`generators/rroms/`](../generators/rroms/): it reads a public list of collections, assigns every row to a console with
page-specific rules, drops collections that the Internet Archive no longer serves, and validates the result. You can use
any language. Please:

- be gentle with `archive.org` (a few requests at a time, a descriptive `User-Agent`);
- never copy file lists into the manifest, only item identifiers;
- run the validator on the output, and fail the build if it is invalid;
- regenerate on a schedule (see `.github/workflows/update-catalog.yml`) because the Internet Archive removes items.

## 10. Responsibility

You are responsible for what your addon points to. Archive Fetcher hosts no files and the addon format cannot contain
any. Point only to items the Internet Archive serves, respect its terms and any takedown it applies, and do not publish
addons that link to content you have no right to share. Users decide which addons they install.

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| The app says the manifest is invalid | Run the validator; the app shows the first problem it found. |
| A console does not appear | It has no collections. (A duplicated console `id` makes the whole manifest invalid.) |
| "N collections could not be loaded" | The item was removed from the Internet Archive, or the network failed. The message lists each one and why; *Retry* helps only with network errors. |
| A collection shows no files | `source.path` does not match any file name in the item (it is case sensitive). |
| Everything is under "locked / login" | The item needs an Internet Archive account; the user can add keys or log in under *Settings*. |
