"""Run the built Kitchen 3D GUI with --factory-startup --python this_file; exits itself."""
import bpy,sys,traceback,tempfile
from pathlib import Path
import blaya,blaya_framework
step=0;tries=0;seen=[];errors=[]
root=Path(tempfile.mkdtemp(prefix='blaya-native-qa-'))
for cls in (blaya_framework.BLAYA_NATIVE_OT_about,blaya_framework.BLAYA_NATIVE_MT_framework):
 def wrap(original,name):
  def draw(self,context):
   try:original(self,context);seen.append(name)
   except Exception:errors.append(traceback.format_exc());traceback.print_exc()
  return draw
 cls.draw=wrap(cls.draw,cls.__name__)

def tick():
 global step,tries
 try:
  if step==0:
   bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
   if blaya.workspace.PENDING is not None or bpy.context.window.workspace.name!='Kitchen 3D':
    tries+=1;assert tries<30;return .25
   if bpy.app.timers.is_registered(blaya_framework.bootstrap):return .25
   assert blaya.industry_active()
   assert '/modules/blaya/' in blaya.__file__
   assert 'blaya' not in bpy.context.preferences.addons
   import addon_utils
   assert 'blaya' not in {module.__name__ for module in addon_utils.modules()}
   assert bpy.context.preferences.blaya.shelf_initialized
   assert f'/Blaya/{bpy.app.version[0]}.{bpy.app.version[1]}' in bpy.utils.resource_path('USER')
   tools = [a for a in bpy.context.screen.areas if a.ui_type == 'BLAYA_TOOLS']
   assert len(tools) == 1
   assert tools[0].x == min(a.x for a in bpy.context.screen.areas)
   assert any(a.type == 'PROPERTIES' and a.ui_type != 'BLAYA_TOOLS' for a in bpy.context.screen.areas)
   from blaya import native_editor
   learning = next(p for p in native_editor.PANELS if p.__name__.endswith('_learning'))
   assert learning.bl_options == {'DEFAULT_CLOSED'}
   bpy.ops.wm.call_menu(name='BLAYA_NATIVE_MT_framework')
   step=1
  elif step==1:
   bpy.ops.blaya_native.about('INVOKE_DEFAULT');step=2
  elif step==2:
   assert len(set(seen))==2 and not errors,(seen,errors)
   # A file with a customized workspace must reopen without factory reshaping.
   bpy.context.window.workspace.name='Asset Layout'
   bpy.ops.wm.save_as_mainfile(filepath=str(root/'asset.blend'))
   bpy.ops.wm.open_mainfile(filepath=str(root/'asset.blend'))
   step=3
  else:
   assert bpy.context.window.workspace.name=='Asset Layout'
   assert 'Kitchen 3D' not in bpy.data.workspaces
   assert blaya.industry_active()
   print('PASS: native bundle, isolated profile, automatic Industry/workspace/native tools editor, menus/credits and saved-file preservation',flush=True)
   bpy.ops.wm.quit_blender();return None
  return .5
 except Exception:
  traceback.print_exc();print('FAIL: native integration step',step,flush=True)
  bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=1,persistent=True)
