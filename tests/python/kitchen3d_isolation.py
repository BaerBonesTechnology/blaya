"""GUI regression for Ctrl-I object/component isolation and restoration."""
import traceback
import bpy
import bmesh
from blaya import isolation, native_editor, workspace
import blaya
attempts=0


def run():
    context=bpy.context
    if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    if context.space_data.local_view:bpy.ops.view3d.localview(frame_selected=False)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    objects=[]
    for x in (0,3,6):
        bpy.ops.mesh.primitive_cube_add(location=(x,0,0));objects.append(context.object)
    for obj in objects:obj.select_set(False)
    a,b,c=objects;a.select_set(True);b.select_set(True);context.view_layer.objects.active=a
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    assert context.space_data.local_view
    assert a.local_view_get(context.space_data) and b.local_view_get(context.space_data)
    assert not c.local_view_get(context.space_data), 'Unselected object was not isolated away'
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    assert not context.space_data.local_view
    b.select_set(False)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='VERT');bpy.ops.mesh.select_all(action='DESELECT')
    bm=bmesh.from_edit_mesh(a.data);bm.verts.ensure_lookup_table()
    bm.verts[0].hide_set(True)
    bm.verts[6].select_set(True)
    before=[[e.hide for e in seq] for seq in (bm.verts,bm.edges,bm.faces)]
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    bm=bmesh.from_edit_mesh(a.data)
    assert sum(not v.hide for v in bm.verts)==1, 'Unselected vertices remain visible'
    assert not c.local_view_get(context.space_data)
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    assert [[e.hide for e in seq] for seq in (bm.verts,bm.edges,bm.faces)]==before
    assert not isolation.isolated(a.data)
    # Restore while leaving Edit Mode; original hidden flags must survive conversion.
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    bpy.ops.object.mode_set(mode='OBJECT')
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    assert [[e.hide for e in seq] for seq in (a.data.vertices,a.data.edges,a.data.polygons)]==before
    assert not isolation.isolated(a.data)
    # Topology can change while isolated without invalidating an index snapshot.
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='DESELECT')
    bm=bmesh.from_edit_mesh(a.data);bm.verts.ensure_lookup_table();bm.verts[6].select_set(True)
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    bm=bmesh.from_edit_mesh(a.data);bm.verts.new((9,9,9));bmesh.update_edit_mesh(a.data)
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    bm=bmesh.from_edit_mesh(a.data)
    assert len(bm.verts)==9 and sum(v.hide for v in bm.verts)==1
    assert not isolation.isolated(a.data)
    # The toggle preserves pre-existing Local View when isolating components inside it.
    bpy.ops.view3d.localview(frame_selected=False)
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    assert context.space_data.local_view
    bpy.ops.view3d.localview(frame_selected=False)
    bpy.ops.mesh.select_all(action='DESELECT')
    assert bpy.ops.blaya.isolate_selection()=={'CANCELLED'}
    assert not isolation.isolated(a.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Edge and face component modes isolate their selected elements too.
    bpy.ops.object.mode_set(mode='EDIT')
    for mode,domain in (('EDGE','edges'),('FACE','faces')):
        bpy.ops.mesh.select_mode(type=mode);bpy.ops.mesh.select_all(action='DESELECT')
        bm=bmesh.from_edit_mesh(a.data)
        next(e for e in getattr(bm,domain) if not e.hide).select_set(True)
        original=[[e.hide for e in seq] for seq in (bm.verts,bm.edges,bm.faces)]
        assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
        assert sum(not e.hide for e in getattr(bm,domain))==1
        assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
        assert [[e.hide for e in seq] for seq in (bm.verts,bm.edges,bm.faces)]==original
    bpy.ops.mesh.select_mode(type='VERT');bpy.ops.object.mode_set(mode='OBJECT')
    # Multi-object component selection sets isolate together.
    for obj in context.selected_objects:obj.select_set(False)
    a.select_set(True);b.select_set(True);context.view_layer.objects.active=a
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='DESELECT')
    meshes=[bmesh.from_edit_mesh(obj.data) for obj in (a,b)]
    for bm in meshes:
        bm.verts.ensure_lookup_table();bm.verts[6].select_set(True)
    context.scene.blaya_workflow.selection_name='Isolate test'
    assert bpy.ops.blaya.workflow(action='SAVE_SET')=={'FINISHED'}
    bpy.ops.mesh.select_all(action='SELECT')
    assert bpy.ops.blaya.workflow(action='LOAD_SET')=={'FINISHED'}
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    assert all(sum(not v.hide for v in bm.verts)==1 for bm in meshes)
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    # Visibility layers follow Blender's undo/redo and remain toggleable afterward.
    names=[a.name,b.name]
    before=[[v.hide for v in bm.verts] for bm in meshes]
    bpy.ops.ed.undo_push(message='Before isolation')
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    bpy.ops.ed.undo_push(message='After isolation')
    assert bpy.ops.ed.undo()=={'FINISHED'}
    meshes=[bmesh.from_edit_mesh(bpy.data.objects[name].data) for name in names]
    assert [[v.hide for v in bm.verts] for bm in meshes]==before
    assert bpy.ops.ed.redo()=={'FINISHED'}
    meshes=[bmesh.from_edit_mesh(bpy.data.objects[name].data) for name in names]
    assert all(sum(not v.hide for v in bm.verts)==1 for bm in meshes)
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    assert [[v.hide for v in bm.verts] for bm in meshes]==before
    # Unregister must release both the visibility snapshot and local-view state.
    assert bpy.ops.blaya.isolate_selection()=={'FINISHED'}
    isolation.unregister()
    assert not context.space_data.local_view
    assert [[v.hide for v in bm.verts] for bm in meshes]==before
    isolation.register()
    bpy.ops.object.mode_set(mode='OBJECT')
    # Registered mode keymaps must take precedence over base select-invert bindings.
    blaya.install_keys()
    for name in ('Object Mode','Mesh'):
        km=context.window_manager.keyconfigs.addon.keymaps[name]
        assert any(k.idname=='blaya.isolate_selection' and k.type=='I' and k.ctrl and k.active for k in km.keymap_items)
    print('PASS: Ctrl-I binding, selected object sets, single vertices, hidden-state restoration, mode changes and topology edits',flush=True)


def tick():
    global attempts
    try:
        if workspace.PENDING or not any(a.type=='VIEW_3D' for a in bpy.context.screen.areas):
            attempts+=1;assert attempts<150;return .2
        with native_editor.override(bpy.context,'MODEL'):run()
    except Exception:
        traceback.print_exc();print('FAIL: Kitchen 3D isolation regression',flush=True)
    bpy.ops.wm.quit_blender();return None

bpy.app.timers.register(tick,first_interval=2)
