# Bundled CAST Maya translator

In a source checkout, this directory contains the CAST Maya translator
distributed with Maya Viewmodel Weapon Toolkit 3.0 and later. Release archives
place runtime copies of `cast.py` and `castplugin.py` in `plug-ins/cod_viewmodel_cast`
while retaining this license and patch record under `third_party/cast`.

## Upstream baseline

- Project: [dtzxporter/cast](https://github.com/dtzxporter/cast)
- Release: [`v2.01`](https://github.com/dtzxporter/cast/releases/tag/v2.01)
- Commit: `363cb39c0425844e29bf4c2457bbbb1d2b9bb4c6`
- Upstream Maya archive SHA-256:
  `cd8f54aeeed68462ea5e0c8edc15fda89cca771abd39b6e6861ab84b2a9fef85`
- Upstream `castplugin.py` SHA-256:
  `0207b3cc18942a40cb86e677530498232243dc9315a887248114ed7ccd5b66ac`
- Unmodified `cast.py` SHA-256:
  `d1ff7fcb2a184f208b21be34485d1863834ae33811078a28a2ccf6ff61f2c577`

The bundled `cast.py` is based on the unchanged v2.00/v2.01 serializer with the
optional-material compatibility patch described below. Its bundled SHA-256 is
`633ab934360aeb04e74eb72e9ad014b5bb8d56acbe452ca1fc4f0166b46231c6`.
The bundled `castplugin.py` is a project-maintained patch with
SHA-256
`bcf5d84ff772d18dc56e6b4af84daf06c7e44c9ea13c44c9dcbb2e02092da656`.

The v2.01 Maya change was selectively merged on top of the ten existing local
patches: [fix skeleton export parent indices](https://github.com/dtzxporter/cast/commit/02a759082b22e278ba8cc2aff4df9169bdfb2195).
Parent lookup now uses the immediate parent joint and full DAG paths, including
joints under non-joint rig groups. This is a correctness fix, not an import
performance claim. Latest-release status was checked on 2026-09-24.

## Local changes to `cast.py`

`Mesh.Material()` and `Hair.Material()` treat a present but empty optional `m`
reference as absent, returning `None`. Exporters may encode an unassigned
material with a zero-element property instead of omitting it. This avoids an
`IndexError` and reuses the importers' existing default-material behavior.
Valid and unresolved hashes, first-value selection, and all binary loading and
saving behavior are unchanged; the getter does not modify the document.

`tests/verify_empty_material_references.py` covers these contracts with real
in-memory binary round trips. `tests/verify_empty_material_host.py` checks Maya
default-material assignment, geometry/skin preservation and scene-only attachment.

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
8. Import skin weights through bounded `MFnSkinCluster.setWeights` blocks
   instead of per-vertex commands. Resolve physical indices from Maya's actual
   influence order, accumulate duplicate slots, disable normalization, and keep
   upstream's rigid-mesh weight of 1.0. Do not change scene evaluation/undo modes.
9. Avoid per-vertex position slicing and per-face-corner nested UV lists when
   preparing mesh buffers. Retain the exact UV table, assignments, normals,
   colors and geometry; short optional UV buffers retain slice-based behavior.
10. Expose an operation-local read session for the toolkit to share parsed CAST
    documents between preflight and import. Revalidate path metadata on reads,
    release on success/error, and never cache ordinary standalone imports.
11. Support package-relative serializer imports for the private toolkit backend,
    while retaining top-level imports for standalone Maya plugin loading.
    Recursive instance imports use the backend's explicit `fileTranslatorName`.
12. Expose `utilityOperationOptions(options=None, runtime=None)` for nested,
    exception-safe per-operation scene/runtime settings. A private import never
    loads or saves `cast.cfg`; standalone registration resolves configuration
    beside its actual registered plugin path, not a hardcoded plugin name.
13. Expose `utilityAnimationTargets(targets)` to map normalized CAST names to
    full Maya DAG paths, with `None` meaning skip and missing keys retaining
    name-based lookup. Node names are never changed. Curve-mode ancestor
    overrides compare mapped paths; explicit blend-shape alias targets restrict
    matching deformers to the mapped mesh's history.
14. Cache DAG, rest-transform, dependency-node and animation-curve lookups only
    within one animation import. Each clip starts with fresh caches even inside
    a shared parse/routing session. Nested target contexts and exceptions restore
    previous state; the progress bar also closes if a curve import raises.
    Non-transform DAG name collisions retain the missing-channel skip behavior
    without creating transform rest data on shapes.
15. Fix the curve-mode override loop so each enabled matching override is
    considered, rather than only the last override in the list. Translation,
    rotation and scale flags remain independent. This is a separately tested
    correctness fix, not a performance optimization.
16. Use absolute active-namespace material names for lookup, creation and slot
    assignment. In Maya relative-name mode, `shadingNode` can return an
    unqualified leaf that subsequently resolves to an existing root material.
    Preserve Maya's unique leaf suffix while qualifying shaders, shading groups
    and their texture/utility nodes against the requested namespace. Build utility
    leaf names from the shader leaf rather than inserting namespace separators
    inside a leaf. The toolkit model gateway isolates names and does not merge an
    existing skeleton; this patch prevents reusing or changing its materials too.
17. Do not require the ShaderFX command for ordinary Standard Surface/Lambert
    materials. Only actual ShaderFX node types request a quoted shader update.
    This avoids aborting texture imports in hosts without ShaderFX loaded.
    Constant-color slots load Maya's bundled `lookdevKit` when `colorConstant`
    is not registered, rather than creating an unknown node in a clean profile.
18. Use complete DAG paths for exported skeleton identities and skin influence
    lookup. Different branches may contain same-named joints with independent
    weights. Preserve all identities and append numeric suffixes to duplicate
    CAST bone names without consuming another bone's original name or renaming
    the live scene. Emit each mesh's explicit `linear` / `quaternion` method.
19. Reject weighted influences missing from the exported skeleton, non-joint
    influences with effective weights, and blended skinning that CAST cannot
    represent. Do not silently redirect unrepresentable weights to bone zero.
    Animated exports with ambiguous joint names are rejected before writing,
    rather than emitting animation tracks inconsistent with renamed model bones.

`tests/verify_skin_weight_roundtrip.py` checks sparse logical influence indices,
same-named DAG joints, all vertex weights, geometry, topology and linear / DQS
round trips, as well as explicit rejection of unsupported skin exports.

`tests/verify_cast_import_gateway.py` covers isolated model creation and material
connections, existing scene preservation, safe single/dual animation, explicit
rejection without external fallback, and operation namespace/option restoration.
The toolkit publishes default model imports at the root with original names or
append-only numeric suffixes, removes its staging namespace, and preserves skin
connections by UUID. Explicit namespace API callers retain isolation.
`tests/verify_cast_duplicate_names.py` checks full duplicate-model weight
independence and rollback after a failure partway through root publication.

`tests/verify_cast_v201.py` covers grouped-joint export parent indices, absolute /
relative / additive mapped animation (translation and quaternion), existing
additive keys, skipped/fallback targets, multiple ancestor overrides and channel
flags, blend-shape target isolation, fresh per-clip caches, nested contexts and
exception restoration. The previous parent algorithm produced `child=-1`
instead of `child=0`; the previous override loop produced translation `4`
instead of `14` for the corresponding fixtures. Both now pass in Maya 2027.

The toolkit also mirrors the active translator's normalization in its model
and animation inventories, rejects ambiguous normalization collisions before
import, and resolves this directory when running directly from a source checkout.

The patched translator remains under the upstream MIT License in
[`LICENSE`](LICENSE). It is not an official dtzxporter CAST build. Report
toolkit-package integration issues in this repository; reproduce issues
against upstream CAST before filing them upstream.

`cast.cfg` is intentionally excluded because it stores per-user preferences.
The obsolete `castpluginoptions.mel` file is not used by CAST v2.01 and is not
distributed.
