"""Native Kitchen 3D modeling and UV workflows."""
import bpy
import bmesh
import textwrap
import json
from .search_map import ENTRIES, BY_ID, search
from .cleanup import RULES, candidates, counts
from . import sculpt_map, uv_orientation, uv_workflow, model_workflow, shelf_workflow, creation, modeling_tools, workspace, finishing, diagnostics, shelf_presets, animation
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, StringProperty

# The shelf stores stable command IDs, never executable Python strings.
COMMANDS = [
    ('freeze', 'Freeze Transforms — Apply Rotation & Scale', 'Transforms'),
    ('origin_center', 'Center Pivot — Origin to Geometry', 'Origin'),
    ('origin_cursor', 'Move Pivot — Origin to 3D Cursor', 'Origin'),
    ('origin_edit', 'Edit Pivot — Toggle Affect Only Origins', 'Origin'),
    ('cursor_selected', 'Snap 3D Cursor to Selection', 'Origin'),
    ('extrude', 'Extrude', 'Model'), ('bevel', 'Bevel', 'Model'),
    ('knife', 'Knife — Multi-Cut', 'Model'),
    ('loop_cut', 'Loop Cut — Insert Edge Loop', 'Model'),
    ('bisect', 'Bisect — Slice Plane', 'Model'),
    ('connect', 'Connect Vertex Path', 'Model'),
    ('bridge', 'Bridge Edge Loops', 'Model'),
    ('grid_fill', 'Grid Fill — Quad Patch', 'Model'),
    ('circularize', 'Circularize — Round Loops and Holes', 'Model'),
    ('relax', 'Relax Edge Chains and Loops', 'Model'),
    ('space', 'Evenly Space Vertices', 'Model'),
    ('straighten', 'Straighten Edge Chains', 'Model'),
    ('edge_slide', 'Slide Edges', 'Edges'),
    ('dissolve', 'Dissolve Selected Components', 'Edges'),
    ('crease', 'Crease Edges', 'Edges'),
    ('flip_normals', 'Flip Selected Face Normals', 'Normals'),
    ('face_orientation', 'Toggle Face Orientation', 'Normals'),
    ('mirror', 'Set Up Mirror', 'Symmetry'),
    ('symmetrize', 'Symmetrize Selection', 'Symmetry'),
    ('merge', 'Merge by Distance — Selected Vertices', 'Cleanup'),
    ('normals', 'Recalculate Outside Normals', 'Cleanup'),
    ('triangulate_ngons', 'Triangulate Selected N-gons Only', 'Cleanup'),
    ('cylinder', 'Add Cylinder — Triangulated Caps', 'Create'),
    ('cone', 'Add Cone — Triangulated Cap', 'Create'),
    ('boundary', 'Inspect Open Boundary Edges', 'Inspect'),
    ('nonmanifold', 'Inspect Non-Manifold Edges', 'Inspect'),
    ('loose', 'Inspect Loose Geometry', 'Inspect'),
    ('ngon', 'Inspect N-gons', 'Inspect'),
    ('degenerate', 'Inspect Zero / Small Area Faces', 'Inspect'),
    ('seam', 'UV — Mark Seam', 'UV'), ('clear_seam', 'UV — Clear Seam', 'UV'),
    ('unwrap', 'UV — Unwrap', 'UV'), ('smart_uv', 'UV — Smart Project', 'UV'),
    ('average_uv', 'UV — Average Island Scale', 'UV'),
    ('pack_uv', 'UV — Pack Islands', 'UV'),
]
COMMANDS.extend((key, 'Add ' + label, 'Create') for key, label, _, _ in creation.PRIMITIVES)
ITEMS = [(key, label, group) for key, label, group in COMMANDS]
LABELS = {key: label for key, label, _ in COMMANDS}
SHORT_LABELS = dict(zip(
    ('freeze','origin_center','origin_cursor','origin_edit','cursor_selected','extrude','bevel',
     'merge','normals','triangulate_ngons','cylinder','cone','boundary','nonmanifold','loose',
     'ngon','degenerate','seam','clear_seam','unwrap','smart_uv','average_uv','pack_uv'),
    ('Freeze','Center Pivot','Pivot to Cursor','Edit Pivot','Cursor to Selection','Extrude','Bevel',
     'Merge','Normals','Fix N-gons','Cylinder','Cone','Boundaries','Non-manifold','Loose',
     'N-gons','Small Faces','Mark Seam','Clear Seam','Unwrap','Smart Project','Match Scale','Pack')))
TOOL_ICONS = {
    'freeze': 'FREEZE', 'origin_center': 'OBJECT_ORIGIN', 'origin_cursor': 'PIVOT_CURSOR',
    'origin_edit': 'TRANSFORM_ORIGINS', 'cursor_selected': 'CURSOR',
    'extrude': 'ORIENTATION_NORMAL', 'bevel': 'EDGE_BEVEL', 'merge': 'AUTOMERGE_ON',
    'normals': 'NORMALS_FACE', 'triangulate_ngons': 'MOD_TRIANGULATE',
    'cylinder': 'MESH_CYLINDER', 'cone': 'MESH_CONE', 'boundary': 'UV_EDGESEL',
    'nonmanifold': 'SELECT_INTERSECT', 'loose': 'UV_VERTEXSEL', 'ngon': 'UV_FACESEL',
    'degenerate': 'SELECT_DIFFERENCE', 'seam': 'EDGE_SEAM', 'clear_seam': 'UV_EDGESEL',
    'unwrap': 'UV', 'smart_uv': 'MOD_UVPROJECT', 'average_uv': 'UV_SYNC_SELECT',
    'pack_uv': 'UV_ISLANDSEL',
}
SHORT_LABELS.update({key: label for key, label, _, _ in creation.PRIMITIVES})
TOOL_ICONS.update({key: icon for key, _, _, icon in creation.PRIMITIVES})
SHORT_LABELS.update({key: label for key, label, _, _, _ in modeling_tools.TOOLS})
TOOL_ICONS.update({key: icon for key, _, icon, _, _ in modeling_tools.TOOLS})
TOOLTIPS = {key: label for key, label, _ in COMMANDS}
TOOLTIPS['add_circle'] = 'Add an unfilled mesh circle. Its open wire edges are intentional; fill it separately if needed.'
TOOLTIPS.update({
    'freeze': 'Apply rotation and scale while preserving location. Requires Object Mode and an unanimated, unconstrained, single-user mesh without armature modifiers.',
    'origin_edit': 'Toggle Affect Only Origins. Turn this off to transform geometry again.',
    'merge': 'Merge selected vertices by distance. Changes geometry; use Undo to reverse.',
    'normals': 'Recalculate outside normals for selected faces. Changes normals; use Undo to reverse.',
    'triangulate_ngons': 'Triangulate only selected, visible n-gons. Existing triangles and quads remain intact. Use Undo to reverse.',
    'cylinder': 'Add a cylinder with triangulated caps instead of n-gons.',
    'cone': 'Add a cone with a triangulated cap instead of an n-gon.',
    'average_uv': 'Average Island Scale: equalize relative UV island scale. Does not set absolute texel density.',
    'seam': 'Mark selected edges as seams for the next unwrap. Does not immediately cut existing UVs.',
})
TOOLTIPS.update({key: description for key, _, _, description, _ in modeling_tools.TOOLS})
for _rule in ('boundary','nonmanifold','loose','ngon','degenerate'):
    TOOLTIPS[_rule] += '. Rechecks current edited meshes and replaces the selection. Hidden geometry is excluded. Categories can overlap; borders and n-gons may be intentional.'


class BLAYA_OT_hint(bpy.types.Operator):
    bl_idname = 'blaya.hint'
    bl_label = 'Help'
    message: StringProperty(options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        return properties.message

    def execute(self, context):
        self.report({'INFO'}, self.message)
        return {'FINISHED'}


def hint(layout, message):
    layout.operator('blaya.hint', text='', icon='INFO', emboss=False).message = message


DEFAULT_SHELF = ('freeze', 'origin_center', 'origin_edit', 'extrude', 'bevel', 'nonmanifold', 'unwrap', 'pack_uv')
KEYMAPS = []
KEYCONFIG_SIGNATURE = None


def prefs(context=None):
    return getattr((context or bpy.context).preferences, "blaya", None)


def tag_redraw(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def remove_keys():
    for keymap, item in KEYMAPS:
        keymap.keymap_items.remove(item)
    KEYMAPS.clear()


def keyconfig_signature():
    active = bpy.context.window_manager.keyconfigs.active
    return (active.name, active.as_pointer()) if active else None


def industry_active(context=None):
    active = (context or bpy.context).window_manager.keyconfigs.active
    return active is not None and active.name == 'Industry_Compatible'


def watch_keyconfig():
    if keyconfig_signature() != KEYCONFIG_SIGNATURE:
        install_keys()
        tag_redraw(bpy.context)
    return 1.0


def draw_keymap_status(layout, context):
    active = context.window_manager.keyconfigs.active
    row = layout.row()
    row.label(text=active.name.replace('_', ' ') if active else 'No keymap')
    hint(row, 'Industry Compatible provides navigation and double-click loop selection. Kitchen 3D adds Shift-Q tools, Ctrl-Space lookup and F8–F11. Save Preferences to retain setup.')
    if not industry_active(context):
        layout.operator('blaya.use_industry_keymap', text='Use Industry Compatible')


class BLAYA_OT_use_industry_keymap(bpy.types.Operator):
    bl_idname = 'blaya.use_industry_keymap'
    bl_label = 'Use Industry Compatible Keymap'
    bl_description = 'Switch Blender to its Industry Compatible preset; save Preferences to retain the choice'

    def execute(self, context):
        configs = context.window_manager.keyconfigs
        existing = configs.get('Industry_Compatible')
        if existing is not None:
            configs.active = existing
        else:
            path = bpy.utils.preset_find('Industry_Compatible', 'keyconfig')
            if not path or not bpy.utils.keyconfig_set(path, report=self.report):
                self.report({'ERROR'}, 'Could not load the bundled Industry Compatible preset')
                return {'CANCELLED'}
        install_keys()
        context.preferences.is_dirty = True
        tag_redraw(context)
        self.report({'INFO'}, 'Industry Compatible active; redundant navigation/tool bindings removed')
        return {'FINISHED'}


def install_keys():
    global KEYCONFIG_SIGNATURE
    remove_keys()
    KEYCONFIG_SIGNATURE = keyconfig_signature()
    config = bpy.context.window_manager.keyconfigs.addon
    settings = prefs()
    if not config or settings is None or not settings.maya_keys:
        return
    view = config.keymaps.new(name='3D View', space_type='VIEW_3D')

    def bind(km, operator, key, **mods):
        item = km.keymap_items.new(operator, key, 'PRESS', **mods)
        KEYMAPS.append((km, item))
        return item

    if not industry_active():
        for key, tool in [('Q', 'builtin.select_box'), ('W', 'builtin.move'), ('E', 'builtin.rotate'), ('R', 'builtin.scale')]:
            bind(view, 'wm.tool_set_by_id', key).properties.name = tool
        bind(view, 'view3d.view_selected', 'F')
        for key, op in [('LEFTMOUSE', 'view3d.rotate'), ('MIDDLEMOUSE', 'view3d.move'), ('RIGHTMOUSE', 'view3d.zoom')]:
            bind(view, op, key, alt=True)
    menu_op = 'wm.call_menu_pie' if settings.space_menu == 'PIE' else 'wm.call_menu'
    bind(view, menu_op, 'Q', shift=True).properties.name = 'BLAYA_MT_context_pie' if settings.space_menu == 'PIE' else 'BLAYA_MT_tools'
    uv_keys = config.keymaps.new(name='UV Editor', space_type='EMPTY')
    bind(uv_keys, 'wm.call_menu_pie', 'Q', shift=True).properties.name = 'BLAYA_MT_context_pie'
    bind(view, 'blaya.map_search', 'SPACE', ctrl=True)
    for name in ('Object Mode', 'Mesh'):
        km = config.keymaps.new(name=name, space_type='EMPTY')
        if not industry_active():
            for key, tool in [('Q', 'builtin.select_box'), ('W', 'builtin.move'), ('E', 'builtin.rotate'), ('R', 'builtin.scale')]:
                bind(km, 'wm.tool_set_by_id', key).properties.name = tool
        for key, mode in [('F8', 'OBJECT'), ('F9', 'VERT'), ('F10', 'EDGE'), ('F11', 'FACE')]:
            bind(km, COMPONENT_OPERATORS[mode], key)


def preferences_updated(self, context):
    if context is not None:
        context.preferences.is_dirty = True
        if context.window_manager is not None:
            tag_redraw(context)


def keys_updated(self, context):
    preferences_updated(self, context)
    install_keys()


class BLAYA_ShelfItem(bpy.types.PropertyGroup):
    command: StringProperty(update=preferences_updated)
    shelf_name: StringProperty(update=preferences_updated, default='Default')
    label: StringProperty(update=preferences_updated)
    icon: StringProperty(update=preferences_updated)
    options: StringProperty(update=preferences_updated, default="{}")
    workflow: StringProperty(update=preferences_updated, default='Model')


class BLAYA_Preferences(bpy.types.PropertyGroup):
    autosave_initialized: BoolProperty(update=preferences_updated, default=False, options={'HIDDEN'})
    native_initialized: BoolProperty(update=preferences_updated, default=False, options={'HIDDEN'})
    maya_keys: BoolProperty(name='Enable Shortcuts', description='Enable viewport shortcuts. Shift-Q opens tools, Ctrl-Space opens the learning map, and F8–F11 select component modes. Disable to restore base bindings.', default=True, update=keys_updated)
    tool_display: EnumProperty(update=preferences_updated, name='Tool Display', items=[
        ('ICONS', 'Icons', 'Compact symbols; hover for tool names and descriptions'),
        ('BOTH', 'Icons + Text', 'Show symbols with short labels'),
        ('TEXT', 'Text', 'Show short labels without symbols')], default='ICONS')
    shelf_name: StringProperty(update=preferences_updated, name='Shelf', default='Default', description='Active named shelf. Enter a new name and add tools to create a shelf')
    space_menu: EnumProperty(name='Context Menu', items=[('PIE','Radial','Context-sensitive native Blender pie menu; hold and gesture or click to choose'),('LIST','List','Modeling and UV tools list')], default='PIE', update=keys_updated)
    shelf: CollectionProperty(type=BLAYA_ShelfItem)
    shelf_initialized: BoolProperty(update=preferences_updated, default=False)
    check_ngons: BoolProperty(update=preferences_updated, name='Check N-gons', default=True,
        description='Include n-gons in cleanup reports; does not change existing geometry automatically')
    area_threshold: FloatProperty(update=preferences_updated, name='Min Area', default=0.00000001, min=0.0, precision=8,
                                  description='Local mesh units squared; object scale is not applied')



class BLAYA_OT_component(bpy.types.Operator):
    bl_idname = 'blaya.component'
    bl_label = 'Component Selection'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=[(x, x.title(), '') for x in ('OBJECT', 'VERT', 'EDGE', 'FACE')])

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH' and context.mode in {'OBJECT', 'EDIT_MESH'}

    def execute(self, context):
        if self.mode == 'OBJECT':
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        else:
            if context.mode != 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type=self.mode)
        return {'FINISHED'}



# Separate operator names let Blender's native keymap list identify each action.
# Keep blaya.component registered for existing scripts and saved custom bindings.
COMPONENT_OPERATORS = {mode: 'blaya.select_' + suffix for mode, suffix in
                       (('OBJECT', 'object'), ('VERT', 'vertex'), ('EDGE', 'edge'), ('FACE', 'face'))}


def component_operator(mode, label):
    def execute(self, context):
        return bpy.ops.blaya.component(mode=mode)

    return type('BLAYA_OT_select_' + mode.lower(), (bpy.types.Operator,), {
        '__module__': __name__,
        'bl_idname': COMPONENT_OPERATORS[mode],
        'bl_label': label + ' Selection',
        'bl_description': 'Switch to ' + label.lower() + ' selection',
        'bl_options': {'REGISTER', 'UNDO'},
        'poll': classmethod(lambda cls, context: BLAYA_OT_component.poll(context)),
        'execute': execute,
    })


COMPONENT_CLASSES = tuple(component_operator(mode, label) for mode, label in
                          (('OBJECT', 'Object'), ('VERT', 'Vertex'), ('EDGE', 'Edge'), ('FACE', 'Face')))


def inspect_mesh(context, rule):
    # Select existing elements only. Inspection never deletes or welds geometry.
    objects = context.objects_in_mode_unique_data
    face_rule = rule in {'ngon', 'degenerate'}
    mode = 'FACE' if face_rule else ('VERT' if rule == 'loose' else 'EDGE')
    bpy.ops.mesh.select_mode(type=mode)
    count = 0
    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        for seq in (bm.faces, bm.edges, bm.verts):
            for item in seq:
                item.select_set(False)
        bm.select_history.clear()
        hits = candidates(bm, rule, prefs(context).area_threshold)
        for item in hits:
            item.select_set(True)
        count += len(hits)
        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return count


class BLAYA_OT_cleanup_scan(bpy.types.Operator):
    bl_idname = 'blaya.cleanup_scan'
    bl_label = 'Scan Edited Meshes'
    bl_description = 'Count visible topology candidates without changing selection or geometry'

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        totals = {rule: 0 for rule, _, _ in RULES}
        objects = []
        threshold = prefs(context).area_threshold
        check_ngons = prefs(context).check_ngons
        for obj in context.objects_in_mode_unique_data:
            report = counts(bmesh.from_edit_mesh(obj.data), threshold)
            objects.append(obj.name)
            for rule, count in report.items():
                totals[rule] += count
        context.window_manager.blaya_cleanup_report = json.dumps({
            'counts': totals, 'objects': objects, 'threshold': threshold, 'check_ngons': check_ngons,
        })
        tag_redraw(context)
        self.report({'INFO'}, f'Scanned {len(objects)} mesh data blocks; selection unchanged')
        return {'FINISHED'}


class BLAYA_PT_cleanup(bpy.types.Panel):
    bl_order = 5
    bl_label = 'Cleanup'
    bl_idname = 'BLAYA_PT_cleanup'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Model'

    def draw(self, context):
        layout = self.layout
        layout.operator('blaya.cleanup_scan', text='Scan', icon='VIEWZOOM')
        diagnostics.draw_cleanup(layout, context)
        if context.mode != 'EDIT_MESH':
            layout.label(text='Edit Mode required')
        settings = prefs(context)
        if settings is None:
            layout.label(text='Initializing…')
            return
        layout.prop(settings, 'check_ngons')
        layout.prop(settings, 'area_threshold')
        raw = context.window_manager.blaya_cleanup_report
        if raw:
            report = json.loads(raw)
            box = layout.box()
            header = box.row()
            header.label(text=f"Last scan: {len(report['objects'])} meshes")
            hint(header, 'Snapshot: rescan after edits or changing objects. Counts exclude hidden geometry and can overlap. Select checks current edited meshes again.')
            for rule, label, unit in RULES:
                if rule == 'ngon' and not report.get('check_ngons', True):
                    continue
                row = box.row(align=True)
                row.label(text=f"{SHORT_LABELS[rule]}: {report['counts'][rule]}")
                action = row.row(align=True)
                action.enabled = context.mode == 'EDIT_MESH'
                action.operator('blaya.command', text='Select').command = rule
        box = layout.box()
        box.label(text='Repair')
        row = box.column(align=True)
        row.enabled = context.mode == 'EDIT_MESH'
        draw_tool_grid(row, ('merge', 'normals', 'triangulate_ngons'))


class BLAYA_OT_command(bpy.types.Operator):
    bl_idname = 'blaya.command'
    bl_label = 'Modeling Tool'
    bl_options = {'REGISTER', 'UNDO'}
    command: EnumProperty(items=ITEMS)

    @classmethod
    def description(cls, context, properties):
        return TOOLTIPS.get(properties.command, 'Run modeling tool')

    def execute(self, context):
        key = self.command
        if key in modeling_tools.BY_KEY:
            return modeling_tools.run(self, context, key)
        if key in creation.OPERATORS:
            if context.area is None or context.area.type != 'VIEW_3D' or context.mode not in {'OBJECT', 'EDIT_MESH'}:
                self.report({'WARNING'}, 'Use a 3D Viewport in Object or mesh Edit Mode')
                return {'CANCELLED'}
            return getattr(bpy.ops.mesh, creation.OPERATORS[key])('EXEC_DEFAULT', location=context.scene.cursor.location)
        if key in {'cylinder', 'cone'}:
            if context.area.type != 'VIEW_3D' or context.mode not in {'OBJECT', 'EDIT_MESH'}:
                self.report({'WARNING'}, 'Use a 3D Viewport in Object or mesh Edit Mode')
                return {'CANCELLED'}
            op = bpy.ops.mesh.primitive_cylinder_add if key == 'cylinder' else bpy.ops.mesh.primitive_cone_add
            return op('EXEC_DEFAULT', end_fill_type='TRIFAN', location=context.scene.cursor.location)
        object_tools = {'freeze', 'origin_center', 'origin_cursor', 'origin_edit'}
        if key in object_tools and (context.mode != 'OBJECT' or not context.selected_objects):
            self.report({'WARNING'}, 'Select an object in Object Mode first')
            return {'CANCELLED'}
        if key not in object_tools | {'cursor_selected'} and context.mode != 'EDIT_MESH':
            self.report({'WARNING'}, 'Select mesh components in Edit Mode first (F9/F10/F11)')
            return {'CANCELLED'}
        try:
            if key == 'freeze':
                if any(o.type != 'MESH' or o.data.users > 1 or o.constraints or o.animation_data
                       or any(m.type == 'ARMATURE' for m in o.modifiers) for o in context.selected_objects):
                    self.report({'WARNING'}, 'Prototype supports unanimated, unconstrained, single-user meshes without armature modifiers')
                    return {'CANCELLED'}
                return bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            if key == 'origin_center':
                return bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
            if key == 'origin_cursor':
                return bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
            if key == 'origin_edit':
                settings = context.scene.tool_settings
                settings.use_transform_data_origin = not settings.use_transform_data_origin
                return {'FINISHED'}
            if key == 'cursor_selected':
                return bpy.ops.view3d.snap_cursor_to_selected()
            if key in {'boundary', 'nonmanifold', 'loose', 'ngon', 'degenerate'}:
                count = inspect_mesh(context, key)
                self.report({'INFO'}, f'{LABELS[key]}: selected {count} elements across edited meshes')
                return {'FINISHED'}
            if key == 'triangulate_ngons':
                repaired = 0
                for obj in context.objects_in_mode_unique_data:
                    bm = bmesh.from_edit_mesh(obj.data)
                    faces = [f for f in bm.faces if f.select and not f.hide and len(f.verts) > 4]
                    repaired += len(faces)
                    if faces:
                        bmesh.ops.triangulate(bm, faces=faces, ngon_method='BEAUTY')
                        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
                self.report({'INFO'}, f'Triangulated {repaired} selected n-gons; existing tris and quads preserved')
                return {'FINISHED'}
            if key == 'normals':
                for obj in context.objects_in_mode_unique_data:
                    bm = bmesh.from_edit_mesh(obj.data)
                    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f.select and not f.hide])
                    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
                return {'FINISHED'}
            operations = {
                'extrude': (bpy.ops.mesh.extrude_region_move, {}),
                'bevel': (bpy.ops.mesh.bevel, {}),
                'merge': (bpy.ops.mesh.remove_doubles, {}),
                'seam': (bpy.ops.mesh.mark_seam, {'clear': False}),
                'clear_seam': (bpy.ops.mesh.mark_seam, {'clear': True}),
                'unwrap': (bpy.ops.uv.unwrap, {}),
                'smart_uv': (bpy.ops.uv.smart_project, {}),
                'average_uv': (bpy.ops.uv.average_islands_scale, {}),
                'pack_uv': (bpy.ops.uv.pack_islands, {}),
            }
            op, kwargs = operations[key]
            return op('INVOKE_DEFAULT', **kwargs)
        except RuntimeError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}


class BLAYA_OT_search(bpy.types.Operator):
    bl_idname = 'blaya.search'
    bl_label = 'Find Maya / Modeling / UV Tool'
    bl_property = 'command'
    command: EnumProperty(items=ITEMS)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context):
        return bpy.ops.blaya.command('EXEC_DEFAULT', command=self.command)


MAP_ITEMS = [(item['id'], item['maya'] + ' → ' + item['blender'], item['aliases']) for item in ENTRIES]


def learning_details(layout, context, item):
    layout.label(text=item['blender'])
    hint(layout, item['where'] + '\n\n' + item['note'])
    command = item['command']
    if command:
        ready = context.mode == item['mode'] and context.active_object is not None
        if item['editor'] == 'UV':
            ready = ready and context.area.type == 'IMAGE_EDITOR' and context.area.ui_type == 'UV'
        else:
            ready = ready and context.area.type == 'VIEW_3D'
        row = layout.row()
        row.enabled = ready
        row.operator('blaya.command', text='Run').command = command
        if not ready:
            layout.label(text='Requires ' + ('UV Editor' if item['editor'] == 'UV' else '3D Viewport') +
                              ' / ' + ('Object Mode' if item['mode'] == 'OBJECT' else 'Mesh Edit Mode'))
        row = layout.row()
        row.operator_context = 'EXEC_DEFAULT'
        row.operator('blaya.shelf_add', text='Add to Shelf').command = command


class BLAYA_OT_map_details(bpy.types.Operator):
    bl_idname = 'blaya.map_details'
    bl_label = 'Maya → Blender Learning Map'
    entry_id: StringProperty(default='freeze')

    @classmethod
    def description(cls, context, properties):
        item = BY_ID.get(properties.entry_id)
        return (item['blender'] + '\n' + item['where'] + '\n\n' + item['note']) if item else 'Find the Blender equivalent'

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=560)

    def draw(self, context):
        item = BY_ID.get(self.entry_id)
        if item:
            learning_details(self.layout, context, item)

    def execute(self, context):
        return {'FINISHED'}


class BLAYA_OT_map_search(bpy.types.Operator):
    bl_idname = 'blaya.map_search'
    bl_label = 'Search Maya → Blender Learning Map'
    bl_property = 'entry_id'
    entry_id: EnumProperty(items=MAP_ITEMS)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context):
        return bpy.ops.blaya.map_details('INVOKE_DEFAULT', entry_id=self.entry_id)


class BLAYA_PT_learning(bpy.types.Panel):
    bl_order = 6
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = 'Learning Map'
    bl_idname = 'BLAYA_PT_learning'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Model'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.window_manager, 'blaya_map_query', text='', icon='VIEWZOOM')
        matches = search(context.window_manager.blaya_map_query)
        layout.label(text=f'{len(matches)} results')
        if not matches:
            layout.label(text='No matches')
        for item in matches:
            box = layout.box()
            box.operator('blaya.map_details', text=item['maya']).entry_id = item['id']



class BLAYA_PT_uv_learning(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = 'Maya → Blender Learning Map'
    bl_region_type = 'UI'
    bl_category = 'UV'
    draw = BLAYA_PT_learning.draw
    bl_idname = 'BLAYA_PT_uv_learning'
    bl_space_type = 'IMAGE_EDITOR'

    @classmethod
    def poll(cls, context):
        return context.area.ui_type == 'UV'


SHELF_ITEMS = [(key, label, group, index) for index, (key, label, group) in enumerate(COMMANDS)]
MODEL_SHELF_ITEMS = [item for item in SHELF_ITEMS if item[2] != 'UV']
UV_SHELF_ITEMS = [item for item in SHELF_ITEMS if item[2] == 'UV']


def shelf_items(self, context):
    return UV_SHELF_ITEMS if self.workflow == 'UV' else MODEL_SHELF_ITEMS if self.workflow == 'MODEL' else SHELF_ITEMS


class BLAYA_OT_shelf_add(bpy.types.Operator):
    bl_idname = 'blaya.shelf_add'
    bl_label = 'Add Tool to Shelf'
    bl_property = 'command'
    workflow: StringProperty(default='ALL')
    command: EnumProperty(items=shelf_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context):
        settings = prefs(context)
        if not any(item.command == self.command and item.shelf_name == settings.shelf_name for item in settings.shelf):
            item = settings.shelf.add()
            item.command = self.command
            item.shelf_name = settings.shelf_name
        context.preferences.is_dirty = True
        tag_redraw(context)
        return {'FINISHED'}


class BLAYA_OT_shelf_edit(bpy.types.Operator):
    bl_idname = 'blaya.shelf_edit'
    bl_label = 'Edit Shelf'
    command: StringProperty()
    action: EnumProperty(items=[('REMOVE', 'Remove', ''), ('UP', 'Move Up', ''), ('DOWN', 'Move Down', '')])

    def execute(self, context):
        shelf = prefs(context).shelf
        index = next((i for i, item in enumerate(shelf) if item.command == self.command and item.shelf_name == prefs(context).shelf_name), -1)
        if index == -1:
            return {'CANCELLED'}
        if self.action == 'REMOVE':
            shelf.remove(index)
        else:
            groups = {item.command: shelf_workflow.metadata(item.command, context)[1] for item in shelf}
            is_uv = groups.get(self.command) == 'UV'
            peers = [i for i, item in enumerate(shelf) if item.shelf_name == prefs(context).shelf_name and (groups.get(item.command) == 'UV') == is_uv]
            position = peers.index(index) + (-1 if self.action == 'UP' else 1)
            if 0 <= position < len(peers):
                shelf.move(index, peers[position])
        context.preferences.is_dirty = True
        tag_redraw(context)
        return {'FINISHED'}


def tool_button(layout, key, force_text=False):
    settings = prefs()
    display = settings.tool_display if settings else 'BOTH'
    item = shelf_presets.item_for(key, bpy.context) if settings else None
    if key.startswith('op:'):
        label = shelf_workflow.metadata(key)[0]
        layout.operator('blaya.custom_run', text=label if force_text or display != 'ICONS' else '', icon=(item.icon if item and item.icon else 'TOOL_SETTINGS') if display != 'TEXT' else 'NONE').operator_id = key[3:]
        return
    label = item.label if item and item.label else SHORT_LABELS.get(key, LABELS[key])
    icon = (item.icon if item and item.icon else TOOL_ICONS[key]) if display != 'TEXT' else 'NONE'
    layout.operator('blaya.command', text=label if force_text or display != 'ICONS' else '', icon=icon).command = key


def draw_tool_grid(layout, keys):
    settings = prefs()
    if settings and settings.tool_display == 'ICONS':
        target = layout.grid_flow(row_major=True, columns=4, even_columns=True, even_rows=True, align=True)
        target.scale_y = 1.35
    else:
        target = layout.column(align=True)
    for key in keys:
        tool_button(target, key)




class BLAYA_MT_tools(bpy.types.Menu):
    bl_label = 'Kitchen 3D — Modeling & UV Tools'
    bl_idname = 'BLAYA_MT_tools'

    def draw(self, context):
        self.layout.operator('blaya.map_search', text='Maya → Blender Learning Map', icon='VIEWZOOM')
        self.layout.operator('blaya.search', text='Run a Tool', icon='TOOL_SETTINGS')
        last_group = None
        for key, label, group in COMMANDS:
            if group != last_group:
                self.layout.separator()
                self.layout.label(text=group)
                last_group = group
            tool_button(self.layout, key, force_text=True)


def draw_shelf(layout, context, workflow):
    settings = prefs(context)
    if settings is None:
        layout.label(text='Initializing…')
        return
    layout.prop(settings, 'shelf_name')
    layout.prop(context.window_manager, 'blaya_edit_shelf', text='Edit Shelf', toggle=True)
    groups = {item.command: shelf_workflow.metadata(item.command, context)[1] for item in settings.shelf}
    visible = [item for item in settings.shelf if item.shelf_name == settings.shelf_name and item.command in groups and
               (groups[item.command] == 'UV') == (workflow == 'UV')]
    if not visible:
        layout.label(text='No favorites')
    if not context.window_manager.blaya_edit_shelf:
        draw_tool_grid(layout, [item.command for item in visible])
    else:
        for item in visible:
            row = layout.row(align=True)
            tool_button(row, item.command, force_text=True)
            row.operator('blaya.shelf_style', text='', icon='PREFERENCES').command = item.command
            for action, icon in [('UP', 'TRIA_UP'), ('DOWN', 'TRIA_DOWN'), ('REMOVE', 'X')]:
                op = row.operator('blaya.shelf_edit', text='', icon=icon)
                op.command, op.action = item.command, action
    row = layout.row(align=True)
    row.operator('blaya.shelf_add', text='Tools', icon='ADD').workflow = workflow
    row.operator('blaya.custom_add', text='Blender', icon='ADD').workflow = 'UV' if workflow == 'UV' else 'Model'
    if context.window_manager.blaya_edit_shelf:
        layout.operator('blaya.capture_tool', text='Capture Last Tool', icon='FILE_TICK').workflow = 'UV' if workflow == 'UV' else 'Model'


class BLAYA_PT_shelf(bpy.types.Panel):
    bl_order = 0
    bl_label = 'Model Shelf'
    bl_idname = 'BLAYA_PT_shelf'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Model'

    def draw(self, context):
        draw_shelf(self.layout, context, 'MODEL')


class BLAYA_PT_model_tools(bpy.types.Panel):
    bl_order = 4
    bl_label = 'Modeling Tools'
    bl_idname = 'BLAYA_PT_model_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Model'

    def draw(self, context):
        self.layout.prop(context.scene.tool_settings, 'use_transform_data_origin', text='Origins Only', toggle=True)
        for group in ('Transforms', 'Origin', 'Model'):
            box = self.layout.box()
            box.label(text=group)
            draw_tool_grid(box, [key for key, _, category in COMMANDS if category == group and key not in modeling_tools.BY_KEY])
        modeling_tools.draw(self.layout, context)


def draw_uv_tools(self, context):
    draw_shelf(self.layout, context, 'UV')
    for title, keys in [('Cut / Seams', ('seam', 'clear_seam')),
                        ('Unwrap', ('unwrap', 'smart_uv')),
                        ('Scale / Pack', ('average_uv', 'pack_uv'))]:
        box = self.layout.box()
        box.label(text=title)
        draw_tool_grid(box, keys)
    hint(self.layout, 'Select mesh faces or UVs before running tools. Orientation colors are available in the UV Editor.')


class BLAYA_PT_uv_shelf(bpy.types.Panel):
    bl_region_type = 'UI'
    bl_category = 'UV'
    bl_label = 'Kitchen 3D UV Tools'
    bl_idname = 'BLAYA_PT_uv_shelf'
    bl_space_type = 'IMAGE_EDITOR'
    bl_order = 0
    draw = draw_uv_tools

    @classmethod
    def poll(cls, context):
        return context.area.ui_type == 'UV'


class BLAYA_PT_view_uv(bpy.types.Panel):
    bl_region_type = 'UI'
    bl_category = 'UV'
    bl_label = 'Kitchen 3D UV Tools'
    bl_idname = 'BLAYA_PT_view_uv'
    bl_space_type = 'VIEW_3D'
    bl_order = 0
    draw = draw_uv_tools


class BLAYA_PT_view_uv_learning(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_region_type = 'UI'
    bl_category = 'UV'
    bl_label = 'Maya → Blender Learning Map'
    bl_idname = 'BLAYA_PT_view_uv_learning'
    bl_space_type = 'VIEW_3D'
    bl_order = 10
    draw = BLAYA_PT_learning.draw


class BLAYA_PT_setup(bpy.types.Panel):
    bl_region_type = 'UI'
    bl_category = 'Setup'
    bl_label = 'Kitchen 3D Setup'
    bl_idname = 'BLAYA_PT_setup'
    bl_space_type = 'VIEW_3D'

    def draw(self, context):
        workspace.draw(self.layout, context)
        draw_keymap_status(self.layout, context)
        box = self.layout.box()
        box.label(text='Auto Save')
        files = context.preferences.filepaths
        box.prop(files, 'use_auto_save_temporary_files', text='Auto Save Recovery Files')
        row = box.row()
        row.enabled = files.use_auto_save_temporary_files
        row.prop(files, 'auto_save_time', text='Minutes')
        box.operator('wm.save_userpref', text='Save Preferences', icon='FILE_TICK')
        settings = prefs(context)
        if settings:
            self.layout.prop(settings, 'maya_keys')
            self.layout.prop(settings, 'tool_display')
            row = self.layout.row(align=True)
            row.operator('blaya.shelf_file', text='Export Shelves', icon='EXPORT').action='EXPORT'
            row.operator('blaya.shelf_file', text='Import', icon='IMPORT').action='IMPORT'


class BLAYA_PT_uv_setup(bpy.types.Panel):
    bl_region_type = 'UI'
    bl_category = 'Setup'
    bl_label = 'Kitchen 3D Setup'
    bl_idname = 'BLAYA_PT_uv_setup'
    bl_space_type = 'IMAGE_EDITOR'
    draw = BLAYA_PT_setup.draw

    @classmethod
    def poll(cls, context):
        return context.area.ui_type == 'UV'


CLASSES = (BLAYA_OT_hint, BLAYA_OT_use_industry_keymap, BLAYA_ShelfItem, BLAYA_Preferences, BLAYA_OT_component, *COMPONENT_CLASSES, BLAYA_OT_command,
           BLAYA_OT_search, BLAYA_OT_shelf_add, BLAYA_OT_shelf_edit, BLAYA_MT_tools,
           BLAYA_PT_shelf, BLAYA_PT_uv_shelf, BLAYA_OT_map_details, BLAYA_OT_map_search,
           BLAYA_PT_learning, BLAYA_PT_uv_learning, BLAYA_OT_cleanup_scan, BLAYA_PT_cleanup, BLAYA_PT_model_tools,
           BLAYA_PT_view_uv, BLAYA_PT_view_uv_learning, BLAYA_PT_setup, BLAYA_PT_uv_setup)


def migrate_preferences():
    """Preserve settings from the first developer build without keeping an add-on."""
    legacy = bpy.context.preferences.addons.get('blaya')
    if legacy is None:
        return
    # Temporarily expose the old serialized settings under their original RNA type.
    compatibility = type('BLAYA_LegacyPreferences', (bpy.types.AddonPreferences,), {
        'bl_idname': 'blaya', '__annotations__': BLAYA_Preferences.__annotations__,
    })
    bpy.utils.register_class(compatibility)
    try:
        old = legacy.preferences
        current = prefs()
        if old:
            for name in BLAYA_Preferences.__annotations__:
                if name == 'shelf':
                    current.shelf.clear()
                    for item in old.shelf:
                        target = current.shelf.add()
                        for field in BLAYA_ShelfItem.__annotations__:
                            setattr(target, field, getattr(item, field))
                else:
                    setattr(current, name, getattr(old, name))
        bpy.context.preferences.addons.remove(legacy)
        bpy.context.preferences.is_dirty = True
    finally:
        bpy.utils.unregister_class(compatibility)


def initialize_preferences():
    settings = prefs()
    if settings is None:
        return 0.1
    if not settings.autosave_initialized:
        files = bpy.context.preferences.filepaths
        files.use_auto_save_temporary_files = True
        files.auto_save_time = 5
        settings.autosave_initialized = True
        bpy.context.preferences.is_dirty = True
    if not settings.shelf_initialized:
        for key in DEFAULT_SHELF:
            settings.shelf.add().command = key
        settings.shelf_initialized = True
    install_keys()
    if not bpy.app.timers.is_registered(watch_keyconfig):
        bpy.app.timers.register(watch_keyconfig, first_interval=1.0, persistent=True)
    return None


def register():
    sculpt_map.register()
    animation.register()
    uv_orientation.register()
    uv_workflow.register()
    model_workflow.register()
    shelf_workflow.register()
    creation.register()
    modeling_tools.register()
    workspace.register()
    finishing.register()
    diagnostics.register()
    shelf_presets.register()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.blaya_map_query = StringProperty(name='Maya or Blender tool',
        description='Search tool names and synonyms; select a result to learn without running it',
        options={'SKIP_SAVE', 'TEXTEDIT_UPDATE'})
    bpy.types.WindowManager.blaya_cleanup_report = StringProperty(options={'SKIP_SAVE'})
    bpy.types.WindowManager.blaya_edit_shelf = BoolProperty(default=False, options={'SKIP_SAVE'})
    bpy.types.Preferences.blaya = bpy.props.PointerProperty(type=BLAYA_Preferences)
    migrate_preferences()
    # Initialize shelves after all native classes have registered.
    bpy.app.timers.register(initialize_preferences, first_interval=0.1)


def unregister():
    if bpy.app.timers.is_registered(watch_keyconfig):
        bpy.app.timers.unregister(watch_keyconfig)
    sculpt_map.unregister()
    animation.unregister()
    shelf_presets.unregister()
    diagnostics.unregister()
    finishing.unregister()
    workspace.unregister()
    modeling_tools.unregister()
    creation.unregister()
    shelf_workflow.unregister()
    model_workflow.unregister()
    uv_workflow.unregister()
    uv_orientation.unregister()
    del bpy.types.WindowManager.blaya_map_query
    del bpy.types.WindowManager.blaya_cleanup_report
    del bpy.types.WindowManager.blaya_edit_shelf
    if bpy.app.timers.is_registered(initialize_preferences):
        bpy.app.timers.unregister(initialize_preferences)
    remove_keys()
    del bpy.types.Preferences.blaya
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
