"""Live topology highlights and read-only UV density measurements."""
import bpy,bmesh,json,math
from .cleanup import candidates,RULES
HANDLE=None
COLORS={'boundary':(1,.6,.05,1),'nonmanifold':(1,.08,.1,1),'loose':(1,.1,1,1),'ngon':(.6,.2,1,1),'degenerate':(1,1,.05,1)}


def overlay_geometry(context):
    from . import prefs
    rule=context.window_manager.blaya_overlay_rule
    result={'lines':[],'points':[]}
    for obj in context.objects_in_mode_unique_data:
        bm=bmesh.from_edit_mesh(obj.data)
        for item in candidates(bm,rule,prefs(context).area_threshold):
            if rule=='loose':result['points'].append(tuple(obj.matrix_world@item.co))
            else:
                edges=item.edges if rule in {'ngon','degenerate'} else [item]
                for edge in edges:result['lines'].extend(tuple(obj.matrix_world@v.co) for v in edge.verts)
    return result


def draw_overlay():
    context=bpy.context
    if not getattr(context.window_manager,'blaya_topology_overlay',False) or context.mode!='EDIT_MESH' or context.area.type!='VIEW_3D' or not context.space_data.overlay.show_overlays:return
    import gpu
    from gpu_extras.batch import batch_for_shader
    data=overlay_geometry(context);shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    blend=gpu.state.blend_get();depth=gpu.state.depth_test_get();width=gpu.state.line_width_get()
    try:
        gpu.state.blend_set('ALPHA');gpu.state.depth_test_set('LESS_EQUAL');gpu.state.line_width_set(3)
        shader.bind();shader.uniform_float('color',COLORS[context.window_manager.blaya_overlay_rule])
        if data['lines']:batch_for_shader(shader,'LINES',{'pos':data['lines']}).draw(shader)
        # Draw small crosses in world units for isolated vertices; no point-size state changes.
        lines=[]
        size=max(context.space_data.region_3d.view_distance*.003,1e-5)
        for point in data['points']:
            for axis in range(3):
                a=list(point);b=list(point);a[axis]-=size;b[axis]+=size;lines.extend((a,b))
        if lines:batch_for_shader(shader,'LINES',{'pos':lines}).draw(shader)
    finally:
        gpu.state.line_width_set(width);gpu.state.depth_test_set(depth);gpu.state.blend_set(blend)


def density_report(context):
    from .uv_workflow import uv_islands,island_areas
    s=context.scene.blaya_uv_settings
    records=[];missing=[]
    for obj in context.objects_in_mode_unique_data:
        bm=bmesh.from_edit_mesh(obj.data);uv=bm.loops.layers.uv.active
        if not uv:missing.append(obj.name);continue
        for island in uv_islands(bm,uv):
            if any(f.hide for f in island):continue
            if not context.scene.tool_settings.use_uv_select_sync and not all(f.select for f in island):continue
            a,w=island_areas(bm,island,uv,obj.matrix_world);w*=context.scene.unit_settings.scale_length**2
            density=s.resolution*math.sqrt(a/w) if min(a,w)>1e-15 else None
            records.append({'object':obj.name,'faces':len(island),'density':density})
    values=[r['density'] for r in records if r['density'] is not None]
    return {'islands':len(records),'collapsed':len(records)-len(values),'missing':missing,
            'min':min(values) if values else None,'max':max(values) if values else None,
            'outside_tolerance':sum(abs(v-s.density)>s.density*.1 for v in values),
            'target':s.density,'resolution':s.resolution,'records':records}


class BLAYA_OT_uv_measure(bpy.types.Operator):
    bl_idname='blaya.uv_measure';bl_label='Measure Density'
    bl_description='Measure fully visible UV islands without changing selection or coordinates. Reports pixels per meter and islands more than 10% from target; rescan after edits'
    @classmethod
    def poll(cls,context):return context.mode=='EDIT_MESH' and context.area and context.area.type=='IMAGE_EDITOR'
    def execute(self,context):
        context.window_manager.blaya_density_report=json.dumps(density_report(context));return {'FINISHED'}


def draw_cleanup(layout,context):
    from . import hint
    row=layout.row(align=True);row.prop(context.window_manager,'blaya_topology_overlay',text='Highlight',toggle=True)
    hint(row,'Live highlight of visible edited geometry without changing selection. Boundaries: orange; non-manifold: red; loose: magenta; n-gons: purple; tiny faces: yellow. Choose one rule. Hidden and occluded geometry is excluded; inspection is not automatic repair.')
    if context.window_manager.blaya_topology_overlay:layout.prop(context.window_manager,'blaya_overlay_rule',text='')


def draw_uv(layout,context):
    from . import hint
    box=layout.box();row=box.row(align=True)
    row.prop(context.space_data.uv_editor,'show_stretch',text='Stretch',toggle=True)
    hint(row,'Native UV stretch colors: blue indicates low distortion, red high distortion. Choose Angle or Area. Disable the separate UV Orientation overlay to avoid mixing colors. Overlap selects problem UV faces; it changes selection, not coordinates.')
    if context.space_data.uv_editor.show_stretch:box.prop(context.space_data.uv_editor,'display_stretch_type',text='Metric')
    row=box.row(align=True);row.operator('blaya.uv_measure',text='Measure',icon='DRIVER_DISTANCE')
    row.operator('blaya.uv_action',text='Overlap',icon='SELECT_INTERSECT').action='OVERLAP'
    raw=context.window_manager.blaya_density_report
    if raw:
        r=json.loads(raw);box.label(text=f"Last scan: {r['islands']} islands")
        if r['min'] is not None:box.label(text=f"{r['min']:.1f}–{r['max']:.1f} px/m")
        row=box.row();row.label(text=f"Off target: {r['outside_tolerance']} · Collapsed: {r['collapsed']}")
        hint(row,f"Snapshot at {r['resolution']}px; target {r['target']:g}px/m, ±10%. Rescan after editing. Missing UV maps: {', '.join(r['missing']) or 'none'}.")


def redraw(self,context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:area.tag_redraw()


def register():
    global HANDLE
    bpy.utils.register_class(BLAYA_OT_uv_measure)
    bpy.types.WindowManager.blaya_topology_overlay=bpy.props.BoolProperty(default=False,options={'SKIP_SAVE'},update=redraw)
    bpy.types.WindowManager.blaya_overlay_rule=bpy.props.EnumProperty(items=[(k,n,'') for k,n,_ in RULES],default='nonmanifold',update=redraw)
    bpy.types.WindowManager.blaya_density_report=bpy.props.StringProperty(options={'SKIP_SAVE'})
    if not bpy.app.background:HANDLE=bpy.types.SpaceView3D.draw_handler_add(draw_overlay,(),'WINDOW','POST_VIEW')


def unregister():
    global HANDLE
    if HANDLE is not None:bpy.types.SpaceView3D.draw_handler_remove(HANDLE,'WINDOW');HANDLE=None
    for name in ('blaya_topology_overlay','blaya_overlay_rule','blaya_density_report'):delattr(bpy.types.WindowManager,name)
    bpy.utils.unregister_class(BLAYA_OT_uv_measure)
