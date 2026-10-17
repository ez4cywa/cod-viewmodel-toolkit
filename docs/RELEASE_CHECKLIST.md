# Release checklist

Use the Maya core `VERSION` as the release version. The build command validates
the other entry points and Blender titles against it; do not copy a version
number from an older verification record.

## Source checks

Run from the repository root with ordinary Python (no host installation needed):

```text
python tests/verify_source_contracts.py
python tests/verify_vendored_cast.py
python tests/verify_empty_material_references.py
python tests/verify_cast_import_names.py
python tests/verify_vendored_blender_cast.py
python tests/verify_build_release.py
python tests/verify_standalone_exports.py
python tests/verify_standalone_export_ui.py
```

- [ ] All source checks pass, including Maya runtime Python 3.7 syntax.
- [ ] Build failure tests preserve existing packages and leave no newly
      published ZIPs; optimized Python still rejects mismatched versions.
- [ ] English/Chinese versions, UI titles and transformations match.
- [ ] Standalone FBX/SMD worker/publication and English/Chinese dialog contracts
      pass, including worker cleanup and plugin-unload window cleanup.
- [ ] Release notes, changelog and bilingual download links use the new tag.
- [ ] No game assets, scene exports, preferences, credentials or personal
      paths are added to the repository.
- [ ] Third-party licenses, pinned source hashes and patch records are current.
      Maya uses private CAST 2.01; Blender retains patched CAST 2.00.

## Host verification

Use isolated profiles and synthetic fixtures. Record the exact host version,
test outcomes and any skipped interaction tests in the release notes.

- [ ] Maya 2027: `mayapy tests/verify_plugin_identity.py` checks English,
      Chinese and legacy entry points and private translator coexistence.
- [ ] For metric-export changes: `mayapy tests/verify_metric_module_path.py`
      and `mayapy tests/verify_maya_units.py` check missing module attributes,
      source-scene preservation and conversions.
- [ ] For animation/backend changes: run the relevant private-backend,
      single/dual, drop, reference-pose and batch-export regressions.
- [ ] For the CAST gateway: `mayapy tests/verify_cast_import_gateway.py`
      verifies private-only imports, no default `cast_import:` prefix, original
      names on first import and append-only numeric collisions (`bone7` →
      `bone71`). Repeated models must retain independent bones/materials/skin
      connections, preserve existing nodes and leave no temporary namespaces.
      Also check explicit namespace API compatibility, single/dual routing,
      rejection of unsupported or ambiguous inputs, and no fallback for rejected
      CAST drops. Record exact entry paths; ordinary File Import is not coverage.
- [ ] Run `mayapy tests/verify_cast_duplicate_names.py` for repeated model
      naming/graph checks and `mayapy tests/verify_skin_weight_roundtrip.py`
      for CAST skin export: compare full bone identities, parent indices,
      per-vertex weights and posed deformation after export/reimport. Include
      distinct DAG bones with the same short name, numeric names, repeated model
      imports and sparse/reordered influences. Confirm exported names are unique
      without renaming the live scene, and `linear` / `quaternion` metadata
      survives. Run focused regressions against source, installed and package
      entries; a successful package load or mesh-count check is insufficient.
      Missing weighted bones, effectively weighted non-joint influences and unsupported blended
      skinning must fail explicitly, not fall back to bone zero.
      Duplicate joint leaf names must conservatively reject animation export,
      including animation-only and unkeyed duplicates, before writing a file.
- [ ] Empty optional Mesh/Hair material references must not raise `IndexError`;
      model meshes without a material use the default material. Check missing,
      empty, valid and unresolved references without modifying source files.
- [ ] For output-default changes: `mayapy tests/verify_optional_outputs.py`
      checks all-off single/dual/quick builds, preference migration, first save
      and rejecting a batch with no selected format.
- [ ] For standalone exports: `mayapy tests/verify_standalone_export_host.py`
      checks both modes, ordinary-scene support, unit conversion, destination
      contents and preservation of live scene state. Repeat with
      `--plugin <entry-path>` for each relevant release or installed entry.
- [ ] Record backend callback/headless animation checks separately from native
      GUI interaction; do not describe a skipped GUI run as accepted.
- [ ] Blender: run applicable assembly, animation and unit tests in Blender
      5.2+; the project's recorded test host is Windows Blender 5.2.1 LTS.
- [ ] Distinguish Python 3.7 syntax compatibility (Maya 2022 target) and older
      Maya 2025 records from this release's actual host coverage.

## Packages

```text
python scripts/build_release.py <new-output-directory>
```

- [ ] The fresh directory contains four platform/language ZIPs. For a
      supplemental Chinese Blender package, use `--blender-zh-only`.
- [ ] Maya packages contain the private `plug-ins/cod_viewmodel_cast` folder
      and adjacent loader, unit helper and `cod_viewmodel_exports.py`; no
      top-level CAST runtime files are distributed.
- [ ] All packages include licenses and notices; exclude `cast.cfg`, obsolete
      options files, bytecode, game assets and user preferences.
- [ ] Expand each Maya package into a disposable directory, then run
      `mayapy tests/verify_release_package.py <expanded-dir> en|zh-CN`.
- [ ] With isolated `BLENDER_USER_SCRIPTS`, run each Blender ZIP using
      `blender --background --factory-startup --python-exit-code 1
      --python tests/verify_blender_release.py -- <zip>`.
- [ ] Produce `SHA256SUMS.txt` for the four final tested archives.

## GitHub publication

- [ ] Review the final diff, confirm a clean commit, and push it with the
      matching version tag to `ez4cywa/cod-viewmodel-toolkit`.
- [ ] GitHub Actions source/build checks pass for that commit.
- [ ] Create the versioned release with four tested ZIPs and checksums.
- [ ] Verify tag/commit, asset names, published state and remote SHA-256
      digests against local files. Download links on both homepages resolve.
