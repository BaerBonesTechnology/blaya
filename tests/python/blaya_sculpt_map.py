"""Run a disposable GUI profile with --factory-startup --python this_file."""
import bpy, traceback
from blaya import sculpt_map, search_map, native_editor, workspace
import blaya_framework
phase=0
seen=set()
errors=[]
map_panel=next(p for p in native_editor.PANELS if p.__name__.endswith('_sculpt_learning'))
assert map_panel.bl_options=={'DEFAULT_CLOSED'}
# Expand only in the disposable test instance so its body is rendered.
bpy.utils.unregister_class(map_panel)
map_panel.bl_options=set()
bpy.utils.register_class(map_panel)
for cls in (map_panel, sculpt_map.BLAYA_OT_sculpt_map_details, blaya_framework.BLAYA_NATIVE_OT_about):
    original=cls.draw
    def wrap(original,name):
        def draw(self,context):
            try:
                original(self,context)
                seen.add(name)
            except Exception:
                errors.append(traceback.format_exc())
                traceback.print_exc()
        return draw
    cls.draw=wrap(original,cls.__name__)

def tick():
    global phase
    try:
        if workspace.PENDING:return .3
        if phase==0:
            assert len(sculpt_map.ENTRIES)==15
            for query,key in [('DynaMesh','dynamesh'),('polygroup','polygroups'),('Grab','move'),('lazy mouse','lazymouse'),('zremeshr','zremesher')]:
                assert search_map.search(query,sculpt_map.ENTRIES)[0]['id']==key,(query,key)
            assert search_map.search('freeze')[0]['id']=='freeze'
            assert blaya_framework._brand_icons['mark'].icon_id
            area=next(a for a in bpy.context.screen.areas if a.ui_type=='BLAYA_TOOLS')
            area.spaces.active.blaya_workflow='SCULPT'
            area.tag_redraw()
            phase=1
            return .6
        if phase==1:
            area=next(a for a in bpy.context.screen.areas if a.ui_type=='BLAYA_TOOLS')
            assert area.spaces.active.blaya_workflow=='SCULPT', area.spaces.active.blaya_workflow
            bpy.ops.screen.screenshot(filepath='/tmp/blaya-sculpt-map-preview.png')
            assert map_panel.__name__ in seen and not errors,(seen,errors)
            bpy.ops.blaya.sculpt_map_details('INVOKE_DEFAULT',entry_id='dynamesh')
            phase=2
            return .6
        if phase==2:
            assert sculpt_map.BLAYA_OT_sculpt_map_details.__name__ in seen and not errors,(seen,errors)
            bpy.ops.blaya_native.about('INVOKE_DEFAULT')
            phase=3
            return .6
        assert blaya_framework.BLAYA_NATIVE_OT_about.__name__ in seen and not errors,(seen,errors)
        bpy.ops.screen.screenshot(filepath='/tmp/blaya-brand-map-preview.png')
        print('PASS: Sculpt map default collapsed, search/typos, Maya search retained, panel/details/About draw and custom brand icon',flush=True)
    except Exception:
        traceback.print_exc()
        print('FAIL: sculpt map UI',flush=True)
    bpy.ops.wm.quit_blender()
    return None
bpy.app.timers.register(tick,first_interval=2)
