# Contributing

Thanks for helping. Most contributions fall into one of these:

## A console is missing from the canonical list

1. Add it to [`spec/platforms.json`](spec/platforms.json) under the right category (or add a category). Use the
   *Manufacturer - Console* naming of No-Intro / Redump and a lower-case id with hyphens.
2. Run `python tools/gen_platforms_doc.py` to refresh `docs/PLATFORMS.md`.
3. Run the tests.

## A row of the reference catalog lands on the wrong console

The reference generator assigns rows with page-specific rules in
[`generators/rroms/classify.py`](generators/rroms/classify.py). Add or reorder a rule (specific rules go first) and add a
test case to `tests/test_rroms.py`. Rebuild with `python generators/rroms/generate.py --verify` and check the diff of
`dist/rroms.addon.json`.

## A broken or removed collection

`--verify` drops collections the Internet Archive no longer serves, so a weekly run fixes most of them. A wrong link
upstream can be corrected with an entry in `PATH_FIXES` in `classify.py`.

## The specification

Changes to [`docs/SPEC.md`](docs/SPEC.md) need matching changes in the validator, the JSON Schema and the tests, and an entry
in the changelog. Additive changes keep `spec` at 1; anything an old app cannot understand needs a new number, and the
app repository has to follow.

## Rules for every change

- `python -m unittest discover -s tests` passes.
- Addons and generators only contain Internet Archive item identifiers: no direct file links, no other hosts, no code.
- Keep the standard-library-only rule for the tools.
