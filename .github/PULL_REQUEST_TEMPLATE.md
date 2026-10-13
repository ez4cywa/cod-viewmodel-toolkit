## Summary

Describe the user-visible change and the workflow it affects.

## Verification

- [ ] Ordinary Python source, vendored-backend and release-build checks pass
- [ ] `mayapy tests/verify_plugin_identity.py` when Maya runtime is affected
- [ ] Relevant host regression passes; state the Maya/Blender version
- [ ] Private backend remains Maya CAST 2.01 / Blender CAST 2.00
- [ ] No proprietary assets, generated outputs, or personal paths added

## Compatibility

Explain any effect on the legacy `attach_gun.py` loader, `attachGun` command,
saved OptionVars, or existing dual-scene metadata.
