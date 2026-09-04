# Release checklist

## Source

- [ ] `VERSION` is exactly `3.0.1` for this release.
- [ ] The primary and legacy loaders both pass the identity test.
- [ ] The Simplified Chinese loader passes identity and localization tests.
- [ ] All distributed Python files parse as Python 3.7 syntax for the Maya
      2022 minimum compatibility target.
- [ ] Single-weapon and both dual-animation modes pass in Maya 2025.
- [ ] The bundled patched CAST 1.99 translator is used for integration tests.
- [ ] `tests/verify_vendored_cast.py` confirms the bundled CAST v1.99 source,
      local patch markers, hashes, and Python 3.7 syntax.
- [ ] User-facing names consistently say Maya Viewmodel Weapon Toolkit.

## Repository hygiene

- [ ] No game assets, exports, verification scenes, archives, or backups.
- [ ] No personal absolute paths, credentials, tokens, or Maya preferences.
- [ ] License and third-party notices are present.
- [ ] The upstream CAST license and patch provenance are included, while
      `cast.cfg` and obsolete `castpluginoptions.mel` remain excluded.
- [ ] English and Chinese installation instructions match current behavior.
- [ ] English and Chinese entry points are documented as mutually exclusive.
- [ ] Compatibility wording distinguishes the Maya 2022/Python 3 expected
      minimum from the Maya 2025/Windows verified release environment.

## GitHub

- [ ] Create the repository as `maya-viewmodel-weapon-toolkit`.
- [ ] Set a concise description and add `maya`, `maya-plugin`, `cast`,
      `animation`, and `game-development` topics.
- [ ] Push the reviewed local `main` branch.
- [ ] Create a `3.0.1` release and attach separate English and Simplified Chinese
      zip archives containing the toolkit and patched CAST runtime files.
- [ ] Test both attached archives in a clean Maya 2025 user profile without a
      separately installed CAST translator.
