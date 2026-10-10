"""Session-only evaluated mesh ghosts; never add scene objects or render geometry."""
import bpy
import numpy as np
from collections import OrderedDict
from .geometry_math import transform_points
from bpy.app.handlers import persistent
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty, PointerProperty

PINK = (1.0, 0.12, 0.48)
GREEN = (0.12, 1.0, 0.32)
HANDLE = None
STATE = {}
MAX_TRIANGLES = 1_000_000
MAX_CACHE_BYTES = 128 * 1024 * 1024
MAX_CACHE_ENTRIES = 128
CACHE = OrderedDict()
CACHE_BYTES = 0
SAMPLING = False
REVISION = 0


def invalidate():
    global CACHE_BYTES, REVISION
    CACHE.clear()
    CACHE_BYTES = 0
    REVISION += 1


def cache_put(key, item):
    global CACHE_BYTES
    size = sum(item[k].nbytes for k in ('vertices', 'triangles', 'edges'))
    # Allow another copy for GPU buffers when a cached pose has been drawn.
    size *= 2
    if size > MAX_CACHE_BYTES:
        return
    previous = CACHE.pop(key, None)
    if previous is not None:
        CACHE_BYTES -= previous[1]
    while CACHE and (CACHE_BYTES + size > MAX_CACHE_BYTES or len(CACHE) >= MAX_CACHE_ENTRIES):
        _, (_, removed) = CACHE.popitem(last=False)
        CACHE_BYTES -= removed
    CACHE[key] = (item, size)
    CACHE_BYTES += size


@persistent
def invalidate_updates(scene, depsgraph):
    if SAMPLING or not active(scene):
        return
    time = (scene.frame_current, scene.frame_subframe)
    if STATE.get('observed_time') != time:
        STATE['observed_time'] = time
        return
    # A stable-frame edit can affect drivers, constraints, rigs, or geometry.
    # Invalidate conservatively rather than displaying an obsolete pose.
    if depsgraph.updates:
        invalidate()
        STATE['signature'] = None



class BLAYA_OnionSettings(bpy.types.PropertyGroup):
    before: IntProperty(name='Before', default=2, min=0, max=8,
                        description='Number of earlier poses')
    after: IntProperty(name='After', default=2, min=0, max=8,
                       description='Number of later poses')
    before_color: FloatVectorProperty(name='Before Color', subtype='COLOR', size=3,
                                      default=PINK, min=0.0, max=1.0,
                                      description='Color of earlier ghost poses',
                                      update=lambda self, context: redraw())
    after_color: FloatVectorProperty(name='After Color', subtype='COLOR', size=3,
                                     default=GREEN, min=0.0, max=1.0,
                                     description='Color of later ghost poses',
                                     update=lambda self, context: redraw())
    step: IntProperty(name='Spacing', default=2, min=1, max=100,
                      description='Frame spacing between ghost poses')
    opacity: FloatProperty(name='Opacity', default=.22, min=.02, max=.8,
                           description='Ghost surface opacity; farther poses fade')


def redraw():
    wm = getattr(bpy.context, 'window_manager', None)
    if wm:
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D' or area.ui_type == 'BLAYA_TOOLS':
                    area.tag_redraw()


def active(scene):
    return bool(STATE) and STATE.get('scene') == scene


def signature(scene):
    s = scene.blaya_onion
    return (scene.frame_current, scene.frame_subframe, s.before, s.after, s.step)


def selected_meshes(context):
    selected = set(context.selected_objects)
    rigs = {obj for obj in selected if obj.type == 'ARMATURE'}
    return [obj for obj in context.view_layer.objects if obj.type == 'MESH'
            and obj.visible_get(view_layer=context.view_layer)
            and (obj in selected or obj.find_armature() in rigs)]


def sample(context, objects, use_cache=False):
    """Snapshot evaluated arrays; cache use is explicit for controlled refreshes."""
    global SAMPLING
    scene = context.scene
    s = scene.blaya_onion
    frame, subframe = scene.frame_current, scene.frame_subframe
    samples, total, active_bytes = [], 0, 0
    SAMPLING = True
    try:
        for direction, count in ((-1, s.before), (1, s.after)):
            for distance in range(1, count + 1):
                target = frame + direction * distance * s.step
                if not scene.frame_start <= target <= scene.frame_end:
                    continue
                depsgraph = None
                for obj in objects:
                    key = (scene.as_pointer(), context.view_layer.as_pointer(), obj.as_pointer(), target, subframe, REVISION)
                    cached = CACHE.get(key) if use_cache else None
                    if cached is not None:
                        item = cached[0]
                        CACHE.move_to_end(key)
                    else:
                        if depsgraph is None:
                            scene.frame_set(target, subframe=subframe)
                            depsgraph = context.evaluated_depsgraph_get()
                        evaluated = obj.evaluated_get(depsgraph)
                        mesh = evaluated.to_mesh()
                        try:
                            if mesh is None:
                                continue
                            mesh.calc_loop_triangles()
                            if total + len(mesh.loop_triangles) > MAX_TRIANGLES:
                                raise RuntimeError('Ghost geometry exceeds 1 million triangles; reduce poses or mesh complexity')
                            vertices = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
                            mesh.vertices.foreach_get('co', vertices)
                            vertices = transform_points(evaluated.matrix_world, vertices.reshape(-1, 3)).astype(np.float32)
                            triangles = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
                            mesh.loop_triangles.foreach_get('vertices', triangles)
                            edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
                            mesh.edges.foreach_get('vertices', edges)
                            item = dict(object=obj, frame=target, vertices=vertices,
                                        triangles=triangles.reshape(-1, 3), edges=edges.reshape(-1, 2), batches=None)
                            if use_cache:
                                cache_put(key, item)
                        finally:
                            evaluated.to_mesh_clear()
                    active_bytes += 2 * sum(item[k].nbytes for k in ('vertices', 'triangles', 'edges'))
                    if active_bytes > MAX_CACHE_BYTES:
                        raise RuntimeError('Ghost geometry exceeds the memory budget; reduce poses or mesh complexity')
                    total += len(item['triangles'])
                    if total > MAX_TRIANGLES:
                        raise RuntimeError('Ghost geometry exceeds 1 million triangles; reduce poses or mesh complexity')
                    # Distance/color belong to this view; geometry/GPU batches belong to a pose.
                    samples.append(dict(item, direction=direction, distance=distance, cached=item))
    finally:
        if scene.frame_current != frame or scene.frame_subframe != subframe:
            scene.frame_set(frame, subframe=subframe)
        STATE['observed_time'] = (frame, subframe)
        SAMPLING = False
    return samples


def refresh(context):
    objects = [obj for obj in STATE['objects'] if obj.name in context.scene.objects]
    if not objects:
        raise RuntimeError('Ghost source meshes are no longer in the scene')
    STATE['samples'] = sample(context, objects, use_cache=True)
    STATE['signature'] = signature(context.scene)
    STATE['pending'] = None
    redraw()


@persistent
def clear(*args):
    invalidate()
    STATE.clear()
    redraw()


def draw():
    context = bpy.context
    if not active(context.scene) or context.view_layer != STATE.get('layer'):
        return
    if (context.screen.is_animation_playing or not context.space_data.overlay.show_overlays
            or signature(context.scene) != STATE.get('signature')):
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    blend, depth, mask = gpu.state.blend_get(), gpu.state.depth_test_get(), gpu.state.depth_mask_get()
    try:
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(False)
        shader.bind()
        for item in STATE['samples']:
            obj = item['object']
            if not obj.visible_get(view_layer=context.view_layer, viewport=context.space_data):
                continue
            cached = item.get('cached', item)
            if not len(item['vertices']):
                cached['batches'] = item['batches'] = ()
                continue
            if cached['batches'] is None:
                cached['batches'] = (
                    batch_for_shader(shader, 'TRIS', {'pos': item['vertices']}, indices=item['triangles']),
                    batch_for_shader(shader, 'LINES', {'pos': item['vertices']}, indices=item['edges']))
            item['batches'] = cached['batches']
            settings = context.scene.blaya_onion
            color = settings.before_color if item['direction'] < 0 else settings.after_color
            alpha = context.scene.blaya_onion.opacity / item['distance'] ** .5
            shader.uniform_float('color', (*color, alpha))
            item['batches'][0].draw(shader)
            shader.uniform_float('color', (*color, min(.85, alpha * 2)))
            item['batches'][1].draw(shader)
    except (ReferenceError, RuntimeError, ValueError):
        clear()
    finally:
        gpu.state.blend_set(blend)
        gpu.state.depth_test_set(depth)
        gpu.state.depth_mask_set(mask)


def tick():
    if not STATE:
        return .2
    try:
        window = STATE['window']
        if window not in list(bpy.context.window_manager.windows):
            clear()
            return .2
        if window.scene != STATE['scene'] or window.view_layer != STATE['layer']:
            return .2
        if window.screen.is_animation_playing:
            return .2
        opacity = window.scene.blaya_onion.opacity
        if STATE.get('opacity') != opacity:
            STATE['opacity'] = opacity
            redraw()
        sig = signature(window.scene)
        if sig != STATE.get('signature'):
            # Wait for one stable timer tick before evaluating frames after a scrub.
            if STATE.get('pending') != sig:
                STATE['pending'] = sig
            else:
                with bpy.context.temp_override(window=window):
                    refresh(bpy.context)
    except (ReferenceError, RuntimeError, ValueError) as error:
        print('Kitchen 3D onion skin:', error)
        clear()
    return .2


class BLAYA_OT_onion_skin(bpy.types.Operator):
    bl_idname = 'blaya.onion_skin'
    bl_label = 'Onion Skin'
    bl_description = 'Toggle earlier and later mesh poses in the chosen colors for the selected meshes or selected rigs; viewport only, hidden during playback'

    @classmethod
    def poll(cls, context):
        return (context.window is not None and context.mode in {'OBJECT', 'POSE'}
                and not context.screen.is_animation_playing)

    def execute(self, context):
        if active(context.scene):
            clear()
            return {'FINISHED'}
        objects = selected_meshes(context)
        if not objects:
            self.report({'WARNING'}, 'Select a mesh or a rig with visible mesh objects')
            return {'CANCELLED'}
        clear()
        STATE.update(scene=context.scene, layer=context.view_layer, window=context.window,
                     objects=objects, samples=[])
        try:
            refresh(context)
        except (RuntimeError, ReferenceError, ValueError) as error:
            clear()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class BLAYA_OT_onion_refresh(bpy.types.Operator):
    bl_idname = 'blaya.onion_refresh'
    bl_label = 'Refresh Ghosts'
    bl_description = 'Rebuild the current ghost sources after editing animation or geometry; toggle off/on to capture a new selection'

    @classmethod
    def poll(cls, context):
        return active(context.scene) and not context.screen.is_animation_playing

    def execute(self, context):
        try:
            invalidate()
            refresh(context)
        except (RuntimeError, ReferenceError, ValueError) as error:
            clear()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


CLASSES = (BLAYA_OnionSettings, BLAYA_OT_onion_skin, BLAYA_OT_onion_refresh)


def register():
    global HANDLE
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blaya_onion = PointerProperty(type=BLAYA_OnionSettings)
    if not bpy.app.background:
        HANDLE = bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_VIEW')
        bpy.app.timers.register(tick, first_interval=.2, persistent=True)
    bpy.app.handlers.depsgraph_update_post.append(invalidate_updates)
    for handlers in (bpy.app.handlers.load_pre, bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        handlers.append(clear)


def unregister():
    global HANDLE
    clear()
    if invalidate_updates in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(invalidate_updates)
    if HANDLE is not None:
        bpy.types.SpaceView3D.draw_handler_remove(HANDLE, 'WINDOW')
        HANDLE = None
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    for handlers in (bpy.app.handlers.load_pre, bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        if clear in handlers:
            handlers.remove(clear)
    del bpy.types.Scene.blaya_onion
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
