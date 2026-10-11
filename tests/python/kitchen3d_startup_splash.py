"""GUI regression: the startup splash must draw after workspace construction."""
# SPDX-License-Identifier: GPL-2.0-or-later
import os
from pathlib import Path
import traceback
import bpy
import blaya_framework
from blaya import workspace

draws = []
originals = []


def track_draw(original):
    def draw(self, context):
        draws.append((context.workspace.name,
                      bpy.app.timers.is_registered(blaya_framework.bootstrap),
                      workspace.PENDING is not None))
        original(self, context)
    return draw


for menu in (bpy.types.WM_MT_splash, bpy.types.WM_MT_splash_quick_setup):
    originals.append((menu, menu.draw))
    menu.draw = track_draw(menu.draw)


def verify():
    try:
        assert draws, 'Startup splash never drew'
        assert all(name == 'Kitchen 3D' and not bootstrap and not pending
                   for name, bootstrap, pending in draws), draws
        assert not bpy.app.timers.is_registered(blaya_framework.show_startup_splash)
        output = Path(os.environ['KITCHEN3D_TEST_OUTPUT'])
        bpy.ops.screen.screenshot(filepath=str(output / 'startup-splash.png'))
        print('PASS: startup splash draws after Kitchen 3D workspace is ready', flush=True)
    except Exception:
        traceback.print_exc()
        print('FAIL: startup splash regression', flush=True)
    finally:
        for menu, original in originals:
            menu.draw = original
        bpy.ops.wm.quit_blender()


bpy.app.timers.register(verify, first_interval=5)
