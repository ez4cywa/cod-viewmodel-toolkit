# Bundled CAST Maya translator

In a source checkout, this directory contains the CAST Maya translator
distributed with Maya Viewmodel Weapon Toolkit 3.0 and later. Release archives
place runtime copies of `cast.py` and `castplugin.py` directly in `plug-ins`
while retaining this license and patch record under `third_party/cast`.

## Upstream baseline

- Project: [dtzxporter/cast](https://github.com/dtzxporter/cast)
- Release: [`v2.00`](https://github.com/dtzxporter/cast/releases/tag/v2.00)
- Commit: `a8ca18a0acf3b97b19332c53b54b47fcc3217755`
- Upstream Maya archive SHA-256:
  `ad2bbe9e30a0ee8182ce33ec1e94f443a9c9878f5012d65cc7ff2b8d26e12d68`
- Upstream `castplugin.py` SHA-256:
  `fcb908ee66a46fa2297b4bcfe8ff8280e3a9df6abce1c31091504126abf67f07`
- Unmodified `cast.py` SHA-256:
  `d1ff7fcb2a184f208b21be34485d1863834ae33811078a28a2ccf6ff61f2c577`

The bundled `cast.py` is byte-for-byte identical to the upstream v2.00
release. The bundled `castplugin.py` is a project-maintained patch with
SHA-256
`27f503383f92d55420f40d91789c3843d0f3efdded1fd681e2054a56bf451712`.

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
6. Restrict sanitized node names to letters, digits, and underscores. Upstream
   v2.00's regular expression still allowed hyphens, which Maya renames again
   and could leave animation tracks without a matching node.
7. Apply the same name normalization to curve-mode override targets.

The toolkit also mirrors the active translator's normalization in its model
and animation inventories, rejects ambiguous normalization collisions before
import, and resolves this directory when running directly from a source checkout.

The patched translator remains under the upstream MIT License in
[`LICENSE`](LICENSE). It is not an official dtzxporter CAST build. Report
toolkit-package integration issues in this repository; reproduce issues
against upstream CAST before filing them upstream.

`cast.cfg` is intentionally excluded because it stores per-user preferences.
The obsolete `castpluginoptions.mel` file is not used by CAST v2.00 and is not
distributed.
