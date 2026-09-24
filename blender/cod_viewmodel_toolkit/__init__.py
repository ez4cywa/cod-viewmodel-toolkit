"""Blender edition of CoD Viewmodel Toolkit."""

bl_info = {
    "name": "CoD Viewmodel Toolkit",
    "author": "ez4cywa",
    "version": (3, 5, 0),
    "blender": (5, 2, 0),
    "location": "3D View > Sidebar > Viewmodel",
    "description": "CAST single/dual weapon assembly and animation batch exports",
    "category": "Import-Export",
    "doc_url": "https://github.com/ez4cywa/cod-viewmodel-toolkit",
}


def register():
    from . import ui
    ui.register()


def unregister():
    from . import ui
    ui.unregister()
