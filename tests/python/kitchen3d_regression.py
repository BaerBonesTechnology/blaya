"""Kitchen 3D --background --factory-startup --python-exit-code 1 --python this_file."""
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
import math
import json
import bpy
import bmesh
import numpy as np
from blaya import circular, loop_tools, onion_skin, workspace, native_editor
from blaya.geometry_math import coordinates, inverse_transform, transform_points, pack_tiles
from blaya.mesh_preview import MeshPreview


class StartupSplashTests(unittest.TestCase):
    def test_waits_for_workspace_then_shows_once(self):
        import blaya_framework
        fake = SimpleNamespace(
            app=SimpleNamespace(background=False, timers=SimpleNamespace(is_registered=Mock(return_value=True))),
            data=SimpleNamespace(filepath=''),
            context=SimpleNamespace(window=object(), preferences=SimpleNamespace(view=SimpleNamespace(show_splash=True))),
            ops=SimpleNamespace(wm=SimpleNamespace(splash=Mock())),
        )
        with patch.object(blaya_framework, 'bpy', fake), patch.object(workspace, 'PENDING', None):
            self.assertEqual(blaya_framework.show_startup_splash(), .2)
            fake.ops.wm.splash.assert_not_called()
            fake.app.timers.is_registered.return_value = False
            with patch.object(workspace, 'PENDING', {'step': 'split'}):
                self.assertEqual(blaya_framework.show_startup_splash(), .2)
                fake.ops.wm.splash.assert_not_called()
            self.assertIsNone(blaya_framework.show_startup_splash())
            fake.ops.wm.splash.assert_called_once_with('INVOKE_DEFAULT')

    def test_respects_preferences_file_open_and_background(self):
        import blaya_framework
        for background, filepath, enabled in ((True, '', True), (False, 'project.blend', True), (False, '', False)):
            fake = SimpleNamespace(
                app=SimpleNamespace(background=background),
                data=SimpleNamespace(filepath=filepath),
                context=SimpleNamespace(preferences=SimpleNamespace(view=SimpleNamespace(show_splash=enabled))),
                ops=SimpleNamespace(wm=SimpleNamespace(splash=Mock())),
            )
            with patch.object(blaya_framework, 'bpy', fake):
                self.assertIsNone(blaya_framework.show_startup_splash())
                fake.ops.wm.splash.assert_not_called()


class ToolRoutingTests(unittest.TestCase):
    def test_argumentless_tools_reset_previous_command(self):
        # UI buttons share the editor_action operator, whose previous properties
        # can contain a modeling command. Exercise the real button adapter.
        for identifier in ('blaya.onion_skin', 'blaya.onion_refresh'):
            properties = SimpleNamespace(arguments='{"command": "relax"}')
            layout = SimpleNamespace(
                operator_context='INVOKE_DEFAULT',
                column=lambda **kwargs: SimpleNamespace(operator=lambda *args, **kwargs: properties),
            )
            native_editor.ToolLayout(layout, 'ANIMATION').operator(identifier)
            self.assertEqual(json.loads(properties.arguments), {})
            self.assertEqual(properties.operator_id, identifier)
            self.assertEqual(properties.workflow, 'ANIMATION')

    def test_parameterized_tools_keep_explicit_arguments(self):
        properties = SimpleNamespace(arguments='{"unrelated": true}')
        layout = SimpleNamespace(
            operator_context='EXEC_DEFAULT',
            column=lambda **kwargs: SimpleNamespace(operator=lambda *args, **kwargs: properties),
        )
        native_editor.ToolLayout(layout, 'MODEL').operator('blaya.command').command = 'relax'
        self.assertEqual(json.loads(properties.arguments), {'command': 'relax'})


class MathTests(unittest.TestCase):
    def test_degenerate_and_invalid_circle(self):
        for points in ([(0,0,0)]*3, [(0,0,0),(1,0,0),(2,0,0)], [(0,0,0),(1,1,0),(np.nan,2,0)]):
            with self.assertRaises(ValueError):circular.circle_points(points)
        result=circular.circle_points([(0,0,0),(1,0,0),(.5,1,0)])
        self.assertTrue(np.isfinite(result).all())

    def test_reflected_transform_roundtrip(self):
        matrix=np.array([[-2,0,0,3],[0,3,0,-2],[0,0,.5,4],[0,0,0,1.]])
        points=np.array([[1,2,3],[-2,4,6],[3,1,-4.]])
        self.assertTrue(np.allclose(transform_points(inverse_transform(matrix),transform_points(matrix,points)),points))
        matrix[2,:]=0
        with self.assertRaises(ValueError):inverse_transform(matrix)

    def test_repeated_path_points(self):
        self.assertTrue(np.allclose(loop_tools.spaced(np.array([[0,0,0],[0,0,0],[3,0,0]]),False)[:,0],[0,1.5,3]))
        with self.assertRaises(ValueError):loop_tools.spaced(np.zeros((3,3)),False)

    def test_udim_padding_occupancy_and_overflow(self):
        positions=pack_tiles([(.6,.6)]*3,1001,.02,{1001,1003})
        self.assertEqual([math.floor(x)+1001+10*math.floor(y) for x,y in positions],[1002,1004,1005])
        positions=pack_tiles([(.2,.2)]*4,1010,.02)
        self.assertTrue(all(9 <= x < 10 and 0 <= y < 1 for x,y in positions))
        with self.assertRaises(ValueError):pack_tiles([(1.1,.2)])
        with self.assertRaises(ValueError):pack_tiles([(.8,.8)]*2,2000)


class Preview(MeshPreview):
    calculate_changes=circular.BLAYA_OT_circularize.calculate_changes
    bl_label='Test Circularize'
    plane='BEST';center_mode='FIT';radius=2.;even=True;flatten=True;influence=1.
    def report(self,*args):pass


def loop_object(name='Loop',offset=0):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([(offset+2,0,0),(offset,1,0),(offset-2,0,0),(offset,-1,0)],[(0,1),(1,2),(2,3),(3,0)],[])
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    return obj


def coords(obj):
    return np.array([tuple(v.co) for v in bmesh.from_edit_mesh(obj.data).verts])


class MeshTests(unittest.TestCase):
    def setUp(self):
        if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        s=bpy.context.scene.blaya_mesh_settings;s.allow_shape_keys=False;s.surface='NONE';s.interaction='DIALOG'

    def edit(self,*objects):
        for obj in objects:obj.select_set(True)
        bpy.context.view_layer.objects.active=objects[0]
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')

    def test_multiobject_and_cancel(self):
        a,b=loop_object('A'),loop_object('B',5);self.edit(a,b)
        before=[coords(o).copy() for o in (a,b)]
        p=Preview();p.capture(bpy.context);p.check(bpy.context)
        for obj in (a,b):
            pts=coords(obj);self.assertTrue(np.allclose(np.linalg.norm(pts-pts.mean(axis=0),axis=1),2))
        p.cancel(bpy.context)
        for obj,original in zip((a,b),before):self.assertTrue(np.allclose(coords(obj),original))

    def test_atomic_invalid_second_object(self):
        a,b=loop_object('A'),loop_object('B');b.scale=(0,1,1);self.edit(a,b)
        original=coords(a).copy()
        self.assertEqual(bpy.ops.blaya.circularize(),{'CANCELLED'})
        self.assertTrue(np.allclose(coords(a),original))

    def test_shape_key_opt_in(self):
        a=loop_object();a.shape_key_add(name='Basis');a.shape_key_add(name='Expression');a.active_shape_key_index=1
        self.edit(a);original=coords(a).copy()
        self.assertEqual(bpy.ops.blaya.circularize(radius=3),{'CANCELLED'})
        self.assertTrue(np.allclose(coords(a),original))
        bpy.context.scene.blaya_mesh_settings.allow_shape_keys=True
        self.assertEqual(bpy.ops.blaya.circularize(radius=3),{'FINISHED'})
        bpy.ops.object.mode_set(mode='OBJECT')
        self.assertTrue(np.allclose([tuple(v.co) for v in a.data.shape_keys.key_blocks['Basis'].data],original))

    def test_topology_guard(self):
        a=loop_object();self.edit(a);p=Preview();p.capture(bpy.context)
        bm=bmesh.from_edit_mesh(a.data);bm.verts.new((8,8,8))
        with self.assertRaises(ValueError):p.restore()

    def test_modal_drag_and_cancel(self):
        a=loop_object();self.edit(a);before=coords(a).copy();p=Preview();p.capture(bpy.context)
        p._area=SimpleNamespace(header_text_set=lambda x:None);p._mouse_x=100;p._initial_value=2.;p._drag_scale=.01;p._drag_property='radius'
        p.check(bpy.context)
        result=p.modal(bpy.context,SimpleNamespace(type='MOUSEMOVE',value='NOTHING',mouse_x=200))
        self.assertEqual(result,{'RUNNING_MODAL'});self.assertAlmostEqual(p.radius,3)
        self.assertTrue(np.allclose(np.linalg.norm(coords(a),axis=1),3))
        self.assertEqual(p.modal(bpy.context,SimpleNamespace(type='ESC',value='PRESS')),{'CANCELLED'})
        self.assertTrue(np.allclose(coords(a),before))

    def test_modal_initial_radius_ignores_object_separation(self):
        a,b=loop_object('A'),loop_object('B',100);self.edit(a,b)
        bpy.context.scene.blaya_mesh_settings.interaction='MODAL'
        context=SimpleNamespace(mode=bpy.context.mode,scene=bpy.context.scene,
            objects_in_mode_unique_data=bpy.context.objects_in_mode_unique_data,
            area=SimpleNamespace(type='VIEW_3D',header_text_set=lambda x:None),
            window_manager=SimpleNamespace(modal_handler_add=lambda x:None))
        p=Preview();p.radius=0
        self.assertEqual(p.invoke(context,SimpleNamespace(mouse_x=100)),{'RUNNING_MODAL'})
        self.assertLess(p.radius,3)
        p.cancel(context)

    def test_modal_plane_strength_and_confirm(self):
        a=loop_object();self.edit(a);p=Preview();p.capture(bpy.context)
        p._area=SimpleNamespace(header_text_set=lambda x:None);p._drag_property='radius'
        p.check(bpy.context)
        p.modal(bpy.context,SimpleNamespace(type='Z',value='PRESS'))
        self.assertEqual(p.plane,'Z')
        p.modal(bpy.context,SimpleNamespace(type='WHEELDOWNMOUSE',value='PRESS'))
        self.assertAlmostEqual(p.influence,.95)
        self.assertEqual(p.modal(bpy.context,SimpleNamespace(type='RET',value='PRESS')),{'FINISHED'})
        self.assertFalse(p._snapshot)

    def test_subdivision_projection_preserves_stack(self):
        bpy.ops.mesh.primitive_cube_add();a=bpy.context.object
        mod=a.modifiers.new('Subdivision','SUBSURF');mod.levels=2
        original_count=len(a.data.vertices)
        self.edit(a)
        bpy.ops.mesh.select_all(action='DESELECT')
        for vertex in bmesh.from_edit_mesh(a.data).verts:vertex.select_set(vertex.co.z > 0)
        bpy.context.scene.blaya_mesh_settings.surface='SUBSURF'
        p=Preview();p.capture(bpy.context)
        self.assertTrue(p._surfaces)
        self.assertEqual(p.execute(bpy.context),{'FINISHED'})
        self.assertTrue(np.isfinite(coords(a)).all())
        self.assertLess(np.max(np.abs(coords(a))),1.01)
        self.assertEqual(len(bmesh.from_edit_mesh(a.data).verts),original_count)
        self.assertEqual(len(a.modifiers),1)
        self.assertEqual(a.modifiers[0].type,'SUBSURF')

    def test_target_projection(self):
        bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,2));target=bpy.context.object;target.select_set(False)
        a=loop_object();self.edit(a);s=bpy.context.scene.blaya_mesh_settings;s.surface='TARGET';s.target=target
        self.assertEqual(bpy.ops.blaya.circularize(radius=2),{'FINISHED'})
        self.assertTrue(np.allclose(coords(a)[:,2],2))


class UVTests(unittest.TestCase):
    setUp = MeshTests.setUp
    edit = MeshTests.edit
    def test_density_presets(self):
        for value in (5.12, 10.24, 20.48):
            self.assertEqual(bpy.ops.blaya.uv_density_preset(density=value), {'FINISHED'})
            self.assertAlmostEqual(bpy.context.scene.blaya_uv_settings.density, value*100, places=3)

    def test_udim_islands_preserve_scale_and_unselected(self):
        from blaya.uv_workflow import distribute_udims, uv_islands
        mesh=bpy.data.meshes.new('UV islands')
        points=[(2*i+x,y,0) for i in range(3) for x,y in ((0,0),(1,0),(1,1),(0,1))]
        mesh.from_pydata(points, [], [tuple(range(i*4,i*4+4)) for i in range(3)])
        obj=bpy.data.objects.new('UV islands',mesh);bpy.context.collection.objects.link(obj);self.edit(obj)
        bm=bmesh.from_edit_mesh(mesh);bm.faces.ensure_lookup_table();uv=bm.loops.layers.uv.verify()
        for i,face in enumerate(bm.faces):
            face.select_set(i<2)
            for loop,point in zip(face.loops,((.1,.1),(.7,.1),(.7,.7),(.1,.7))):loop[uv].uv=point
        bpy.context.scene.tool_settings.use_uv_select_sync=True
        original=np.array([tuple(l[uv].uv) for l in bm.faces[2].loops])
        self.assertEqual([next(iter(island)) for island in uv_islands(bm, uv)], list(bm.faces))
        count,skipped=distribute_udims(bpy.context,bpy.context.scene.blaya_uv_settings)
        self.assertEqual((count,skipped),(2,0))
        for face,tile in zip(list(bm.faces)[:2],(1,2)):
            coords=np.array([tuple(l[uv].uv) for l in face.loops]);self.assertEqual(math.floor(coords[:,0].min()),tile)
            self.assertTrue(np.allclose(np.ptp(coords,axis=0),(.6,.6)))
        self.assertTrue(np.allclose([tuple(l[uv].uv) for l in bm.faces[2].loops],original))
        # An oversized island rejects the entire operation before any UV changes.
        for loop in bm.faces[1].loops:loop[uv].uv.x*=3
        before=[tuple(l[uv].uv) for f in bm.faces for l in f.loops]
        with self.assertRaises(ValueError):distribute_udims(bpy.context,bpy.context.scene.blaya_uv_settings)
        self.assertTrue(np.allclose([tuple(l[uv].uv) for f in bm.faces for l in f.loops],before))


class OnionTests(unittest.TestCase):
    def setUp(self):
        if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        onion_skin.clear();bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add();self.obj=bpy.context.object
        scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=20;scene.frame_set(10)
        scene.blaya_onion.before=2;scene.blaya_onion.after=2;scene.blaya_onion.step=1
        onion_skin.STATE.update(scene=scene,layer=bpy.context.view_layer,objects=[self.obj],samples=[])

    def tearDown(self):onion_skin.clear()

    def test_cache_hits_invalidation_and_frame_restore(self):
        calls=[];original=onion_skin.transform_points
        def counted(*args):calls.append(1);return original(*args)
        onion_skin.transform_points=counted
        try:
            first=onion_skin.sample(bpy.context,[self.obj],use_cache=True)
            self.assertEqual(len(calls),4)
            second=onion_skin.sample(bpy.context,[self.obj],use_cache=True)
            self.assertEqual(len(calls),4)
            self.assertIs(first[0]['vertices'],second[0]['vertices'])
            self.assertEqual(bpy.context.scene.frame_current,10)
            bpy.context.scene.frame_set(11)
            onion_skin.sample(bpy.context,[self.obj],use_cache=True)
            self.assertEqual(len(calls),6, 'Overlapping frames should reuse cached poses')
            self.obj.location.x=4;bpy.context.view_layer.update()
            self.assertFalse(onion_skin.CACHE, 'Geometry/transform edit must invalidate cached poses')
            onion_skin.sample(bpy.context,[self.obj],use_cache=True)
            self.assertEqual(len(calls),10)
        finally:onion_skin.transform_points=original

    def test_empty_evaluated_mesh(self):
        mesh=bpy.data.meshes.new('Empty');self.obj.data=mesh
        samples=onion_skin.sample(bpy.context,[self.obj],use_cache=True)
        self.assertEqual(len(samples),4)
        self.assertTrue(all(s['vertices'].shape==(0,3) for s in samples))
        self.assertEqual(bpy.context.scene.frame_current,10)

    def test_budget_failure_restores_frame(self):
        limit=onion_skin.MAX_TRIANGLES;onion_skin.MAX_TRIANGLES=1
        try:
            with self.assertRaises(RuntimeError):onion_skin.sample(bpy.context,[self.obj])
            self.assertEqual(bpy.context.scene.frame_current,10)
        finally:onion_skin.MAX_TRIANGLES=limit


class LifecycleTests(unittest.TestCase):
    def test_workspace_waits_by_elapsed_time(self):
        window=SimpleNamespace(workspace=object())
        wm=SimpleNamespace(windows=[window],blaya_workspace_error='')
        fake_bpy=SimpleNamespace(context=SimpleNamespace(window_manager=wm))
        pending=workspace.PENDING
        try:
            workspace.PENDING={'window':window,'expected':object(),'phase':'duplicate'}
            with patch.object(workspace,'bpy',fake_bpy), patch.object(workspace.time,'monotonic',return_value=0):
                self.assertEqual(workspace.build_pending(),.1)
            with patch.object(workspace,'bpy',fake_bpy), patch.object(workspace.time,'monotonic',return_value=4):
                for i in range(100):self.assertEqual(workspace.build_pending(),.1)
                self.assertIsNotNone(workspace.PENDING)
            with patch.object(workspace,'bpy',fake_bpy), patch.object(workspace.time,'monotonic',return_value=31):
                self.assertIsNone(workspace.build_pending())
                self.assertIsNone(workspace.PENDING)
                self.assertIn('did not complete',wm.blaya_workspace_error)
        finally:workspace.PENDING=pending

    def test_onion_cache_bound_and_clear(self):
        onion_skin.invalidate()
        old=onion_skin.MAX_CACHE_BYTES;onion_skin.MAX_CACHE_BYTES=1000
        try:
            for i in range(30):onion_skin.cache_put(i,dict(vertices=np.zeros((10,3),np.float32),triangles=np.zeros((2,3),np.int32),edges=np.zeros((2,2),np.int32)))
            self.assertLessEqual(onion_skin.CACHE_BYTES,1000)
            self.assertLess(len(onion_skin.CACHE),30)
            onion_skin.clear();self.assertFalse(onion_skin.CACHE);self.assertEqual(onion_skin.CACHE_BYTES,0)
        finally:onion_skin.MAX_CACHE_BYTES=old

    def test_unregister_register_handlers(self):
        for module,handler,handlers in ((onion_skin,onion_skin.invalidate_updates,bpy.app.handlers.depsgraph_update_post),(workspace,workspace.cancel_pending,bpy.app.handlers.load_pre)):
            module.unregister();self.assertNotIn(handler,handlers)
            module.register();self.assertEqual(list(handlers).count(handler),1)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__)))
    if not result.wasSuccessful():raise AssertionError('Kitchen 3D regressions failed')
