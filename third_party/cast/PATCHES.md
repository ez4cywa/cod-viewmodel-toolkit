# Bundled CAST Maya translator

In a source checkout, this directory contains the CAST Maya translator
distributed with Maya Viewmodel Weapon Toolkit 3.0. Release archives place
runtime copies of `cast.py` and `castplugin.py` directly in `plug-ins` while
retaining this license and patch record under `third_party/cast`.

## Upstream baseline

- Project: [dtzxporter/cast](https://github.com/dtzxporter/cast)
- Release: [`v1.99`](https://github.com/dtzxporter/cast/releases/tag/v1.99)
- Commit: `bf6da852b73d5bd1e94140949a44fe20dd56eed0`
- Upstream Maya archive SHA-256:
  `ed4a1cb5862dcba4fb76b3487e4f821c0f4b12094ca1147cd7e3285ae6cb5005`
- Upstream `castplugin.py` SHA-256:
  `5e6266af4dbc3fc7386caaaf9dd1d7105ed03b9e37cf5243ed38a95c268ba8cd`
- Unmodified `cast.py` SHA-256:
  `d1ff7fcb2a184f208b21be34485d1863834ae33811078a28a2ccf6ff61f2c577`

The bundled `cast.py` is byte-for-byte identical to the upstream v1.99
release. The bundled `castplugin.py` is a project-maintained patch with
SHA-256
`7f57829bc05978d817af93caeeaea7566baf0959b783df5b82747a7fbd279a06`.

## Local changes to `castplugin.py`

1. Skip Maya menu and progress-bar UI in batch mode.
2. Treat missing per-vertex UV assignments as Maya UV `(0, 0)` during export,
   report affected vertices, and continue instead of aborting the export.
3. Honor explicit per-call import options for `importIK`,
   `importConstraints`, `importAtTime`, `importReset`, and `importLooping`.
4. Honor explicit per-call export options for `exportModel`, `exportAnim`, and
   `bakeKeyframes`.
5. Restore the translator's previous in-memory settings after each scripted
   import or export, without rewriting `cast.cfg`.

The patched translator remains under the upstream MIT License in
[`LICENSE`](LICENSE). It is not an official dtzxporter CAST build. Report
toolkit-package integration issues in this repository; reproduce issues
against upstream CAST before filing them upstream.

`cast.cfg` is intentionally excluded because it stores per-user preferences.
The obsolete `castpluginoptions.mel` file is not used by CAST v1.99 and is not
distributed.
