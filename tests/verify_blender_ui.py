"""Interactive Blender screenshot smoke test using a factory profile.

Set COD_VWT_UI_DIR. This test exits Blender; never use a session with unsaved work.
"""

import json
import os
from pathlib import Path
import sys
import traceback

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
import cod_viewmodel_toolkit

OUTPUT = Path(os.environ["COD_VWT_UI_DIR"])
OUTPUT.mkdir(parents=True, exist_ok=True)
cod_viewmodel_toolkit.register()
bpy.context.preferences.view.show_splash = False
step = 0


def capture():
    global step
    try:
        area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
        area.spaces.active.show_region_ui = True
        region = next(region for region in area.regions if region.type == "UI")
        if step == 0:
            # Test-only native input, with --enable-event-simulate. Coordinates
            # match the factory 1280x900 screenshot and the observed tab.
            for value in ("PRESS", "RELEASE"):
                bpy.context.window.event_simulate(type="ESC", value=value)
            step += 1
            return 1.0
        if step == 1:
            bpy.context.window.event_simulate(type="MOUSEMOVE", value="NOTHING",
                                              x=1037, y=568)
            step += 1
            return 1.0
        if step == 2:
            for value in ("PRESS", "RELEASE"):
                bpy.context.window.event_simulate(type="LEFTMOUSE", value=value,
                                                  x=1037, y=568)
            step += 1
            return 1.0
        if step == 3:
            bpy.ops.screen.screenshot(filepath=str(OUTPUT / "single.png"))
            bpy.context.scene.cod_vwt.mode = "DUAL"
            step += 1
            area.tag_redraw()
            return 1.0
        if step == 4:
            bpy.ops.screen.screenshot(filepath=str(OUTPUT / "dual.png"))
            (OUTPUT / "ui.json").write_text(json.dumps({
                "version": bpy.app.version_string,
                "sidebar_width": region.width, "category": region.active_panel_category,
                "window": [bpy.context.window.width, bpy.context.window.height],
                "single_and_dual": region.active_panel_category == "Viewmodel"}), encoding="utf-8")
            bpy.ops.wm.quit_blender()
        return None
    except Exception:
        (OUTPUT / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(capture, first_interval=3.0)
