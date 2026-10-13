# Release checklist

Use the Maya core `VERSION` as the release version. The build command validates
the other entry points and Blender titles against it; do not copy a version
number from an older verification record.

## Source checks

Run from the repository root with ordinary Python (no host installation needed):

```text
python tests/verify_source_contracts.py
python tests/verify_vendored_cast.py
python tests/verify_vendored_blender_cast.py
python tests/verify_build_release.py
```

- [ ] All source checks pass, including Maya runtime Python 3.7 syntax.
- [ ] Build failure tests preserve existing packages and leave no newly
      published ZIPs; optimized Python still rejects mismatched versions.
- [ ] English/Chinese versions, UI titles and transformations match.
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
      and adjacent loader; no top-level CAST runtime files are distributed.
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
