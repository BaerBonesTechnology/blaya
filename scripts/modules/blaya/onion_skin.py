"""Session-only evaluated mesh ghosts; never add scene objects or render geometry."""
import bpy
from bpy.app.handlers import persistent
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty, PointerProperty

PINK = (1.0, 0.12, 0.48)
GREEN = (0.12, 1.0, 0.32)
HANDLE = None
STATE = {}
MAX_TRIANGLES = 1_000_000


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


def sample(context, objects):
    """Snapshot world-space evaluated triangles, restoring frame even on failure."""
    scene = context.scene
    s = scene.blaya_onion
    frame, subframe = scene.frame_current, scene.frame_subframe
    samples = []
    total = 0
    try:
        for direction, count in ((-1, s.before), (1, s.after)):
            for distance in range(1, count + 1):
                target = frame + direction * distance * s.step
                if not scene.frame_start <= target <= scene.frame_end:
                    continue
                scene.frame_set(target, subframe=subframe)
                depsgraph = context.evaluated_depsgraph_get()
                for obj in objects:
                    evaluated = obj.evaluated_get(depsgraph)
                    mesh = evaluated.to_mesh()
                    try:
                        if mesh is None:
                            continue
                        mesh.calc_loop_triangles()
                        total += len(mesh.loop_triangles)
                        if total > MAX_TRIANGLES:
                            raise RuntimeError('Ghost geometry exceeds 1 million triangles; reduce poses or mesh complexity')
                        matrix = evaluated.matrix_world.copy()
                        vertices = [tuple(matrix @ vertex.co) for vertex in mesh.vertices]
                        triangles = [tuple(tri.vertices) for tri in mesh.loop_triangles]
                        edges = [tuple(edge.vertices) for edge in mesh.edges]
                        samples.append(dict(object=obj, frame=target, direction=direction,
                                            distance=distance, vertices=vertices,
                                            triangles=triangles, edges=edges, batches=None))
                    finally:
                        evaluated.to_mesh_clear()
    finally:
        scene.frame_set(frame, subframe=subframe)
    return samples


def refresh(context):
    objects = [obj for obj in STATE['objects'] if obj.name in context.scene.objects]
    if not objects:
        raise RuntimeError('Ghost source meshes are no longer in the scene')
    STATE['samples'] = sample(context, objects)
    STATE['signature'] = signature(context.scene)
    STATE['pending'] = None
    redraw()


@persistent
def clear(*args):
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
            if item['batches'] is None:
                item['batches'] = (
                    batch_for_shader(shader, 'TRIS', {'pos': item['vertices']}, indices=item['triangles']),
                    batch_for_shader(shader, 'LINES', {'pos': item['vertices']}, indices=item['edges']))
            settings = context.scene.blaya_onion
            color = settings.before_color if item['direction'] < 0 else settings.after_color
            alpha = context.scene.blaya_onion.opacity / item['distance'] ** .5
            shader.uniform_float('color', (*color, alpha))
            item['batches'][0].draw(shader)
            shader.uniform_float('color', (*color, min(.85, alpha * 2)))
            item['batches'][1].draw(shader)
    except (ReferenceError, RuntimeError):
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
    except (ReferenceError, RuntimeError) as error:
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
        except (RuntimeError, ReferenceError) as error:
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
            refresh(context)
        except (RuntimeError, ReferenceError) as error:
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
    for handlers in (bpy.app.handlers.load_pre, bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        handlers.append(clear)


def unregister():
    global HANDLE
    clear()
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
