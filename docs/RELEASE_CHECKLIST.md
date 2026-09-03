# Release checklist

## Source

- [ ] `VERSION` is exactly `3.0` for this release.
- [ ] The primary and legacy loaders both pass the identity test.
- [ ] Single-weapon and both dual-animation modes pass in Maya 2025.
- [ ] CAST translator 1.99 or newer is used for integration tests.
- [ ] User-facing names consistently say Maya Viewmodel Weapon Toolkit.

## Repository hygiene

- [ ] No game assets, exports, verification scenes, archives, or backups.
- [ ] No personal absolute paths, credentials, tokens, or Maya preferences.
- [ ] License and third-party notices are present.
- [ ] English and Chinese installation instructions match current behavior.

## GitHub

- [ ] Create the repository as `maya-viewmodel-weapon-toolkit`.
- [ ] Set a concise description and add `maya`, `maya-plugin`, `cast`,
      `animation`, and `game-development` topics.
- [ ] Push the reviewed local `main` branch.
- [ ] Create a `3.0` release and attach a zip containing only repository files.
- [ ] Test the attached archive in a clean Maya 2025 user profile.
