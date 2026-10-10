"""Shelf appearance and safe, data-only native operator presets."""
import bpy,json,re,math
from bpy.props import StringProperty,EnumProperty,IntProperty
ICONS=[]


def item_for(command,context):
    from . import prefs
    p=prefs(context)
    return next((i for i in p.shelf if i.command==command and i.shelf_name==p.shelf_name),None)


def icon_items(self,context):return ICONS


def serial_options(properties):
    result={}
    for p in properties.bl_rna.properties:
        if p.identifier=='rna_type' or p.is_readonly or p.type not in {'BOOLEAN','INT','FLOAT','STRING','ENUM'}:continue
        value=getattr(properties,p.identifier)
        if isinstance(value,set):value=sorted(value)
        elif getattr(p,'is_array',False):value=list(value)
        result[p.identifier]=value
    return result


def validate_options(operator_id,values):
    if not isinstance(values,dict) or len(values)>200:raise ValueError('Invalid tool options')
    module,name=operator_id.split('.')
    rna=getattr(getattr(bpy.ops,module),name).get_rna_type();result={}
    for key,value in values.items():
        p=rna.properties.get(key)
        if not p or p.is_readonly or p.type not in {'BOOLEAN','INT','FLOAT','STRING','ENUM'}:raise ValueError('Unsupported saved option: '+key)
        vals=value if isinstance(value,list) else [value]
        if getattr(p,'is_array',False) and (not isinstance(value,list) or len(value)!=p.array_length):raise ValueError('Invalid array: '+key)
        if not getattr(p,'is_array',False) and p.type!='ENUM' and isinstance(value,list):raise ValueError('Invalid scalar: '+key)
        if p.type=='BOOLEAN' and any(type(v)!=bool for v in vals):raise ValueError('Invalid toggle: '+key)
        if p.type in {'INT','FLOAT'}:
            if any(type(v) not in ({int} if p.type=='INT' else {int,float}) or not math.isfinite(v) or v<p.hard_min or v>p.hard_max for v in vals):raise ValueError('Invalid number: '+key)
        if p.type=='STRING' and (not isinstance(value,str) or len(value)>8192):raise ValueError('Invalid text: '+key)
        if p.type=='ENUM':
            if p.is_enum_flag:
                if not isinstance(value,list):raise ValueError('Invalid flags: '+key)
                value=set(value)
            elif not isinstance(value,str):raise ValueError('Invalid choice: '+key)
            # Dynamic enums can be empty outside their operator context; Blender validates these at execution.
            choices={e.identifier for e in p.enum_items}
            if choices and any(v not in choices for v in vals):raise ValueError('Unknown choice: '+key)
        result[key]=value
    return result


class BLAYA_OT_shelf_style(bpy.types.Operator):
    bl_idname='blaya.shelf_style';bl_label='Customize Shelf Tool'
    command:StringProperty()
    label:StringProperty(name='Label')
    icon:EnumProperty(name='Symbol',items=icon_items)
    position:IntProperty(name='Position',min=1,default=1)
    @classmethod
    def description(cls,context,p):return 'Change this shelf entry’s label, native symbol, and position; tool behavior remains unchanged'
    def invoke(self,context,event):
        from . import prefs,SHORT_LABELS,TOOL_ICONS
        item=item_for(self.command,context)
        if item is None:return {'CANCELLED'}
        self.label=item.label or SHORT_LABELS.get(self.command,self.command[3:])
        self.icon=item.icon or TOOL_ICONS.get(self.command,'TOOL_SETTINGS')
        from .shelf_workflow import metadata
        is_uv=metadata(item.command,context)[1]=='UV'
        peers=[i for i in prefs(context).shelf if i.shelf_name==item.shelf_name and (metadata(i.command,context)[1]=='UV')==is_uv]
        self.position=next((n+1 for n,i in enumerate(peers) if i==item),1)
        return context.window_manager.invoke_props_dialog(self)
    def draw(self,context):
        self.layout.prop(self,'label');self.layout.prop(self,'icon');self.layout.prop(self,'position')
    def execute(self,context):
        from . import prefs,tag_redraw
        item=item_for(self.command,context)
        if item is None:return {'CANCELLED'}
        item.label=self.label;item.icon=self.icon
        shelf=prefs(context).shelf
        from .shelf_workflow import metadata
        is_uv=metadata(item.command,context)[1]=='UV'
        peers=[n for n,i in enumerate(shelf) if i.shelf_name==item.shelf_name and (metadata(i.command,context)[1]=='UV')==is_uv]
        source=next(n for n,i in enumerate(shelf) if i==item)
        shelf.move(source,peers[min(self.position-1,len(peers)-1)])
        context.preferences.is_dirty=True;tag_redraw(context);return {'FINISHED'}


class BLAYA_OT_capture_tool(bpy.types.Operator):
    bl_idname='blaya.capture_tool';bl_label='Capture Last Blender Tool'
    bl_description='Save the most recent native undoable operator and its scalar options to this shelf. Re-run the tool and capture again to update options. Pointer properties and macro operators are unsupported'
    workflow:StringProperty(default='Model')
    def execute(self,context):
        from . import prefs,tag_redraw
        native=next((op for op in reversed(context.window_manager.operators) if not op.bl_idname.startswith('BLAYA_OT_')),None)
        if native is None:self.report({'WARNING'},'Run a native Blender tool first');return {'CANCELLED'}
        identifier=native.bl_idname
        module,separator,name=identifier.partition('_OT_')
        if not separator:self.report({'WARNING'},'Unsupported operator');return {'CANCELLED'}
        operator_id=module.lower()+'.'+name
        try:
            if len(native.macros):raise ValueError('Macro tools are unsupported; capture a single operation')
            options=serial_options(native.properties);validate_options(operator_id,options)
        except (ValueError,TypeError,AttributeError,KeyError) as error:
            self.report({'WARNING'},str(error));return {'CANCELLED'}
        command='op:'+operator_id;item=item_for(command,context)
        if item is None:item=prefs(context).shelf.add();item.command=command;item.shelf_name=prefs(context).shelf_name
        item.workflow=self.workflow;item.label=native.bl_label;item.options=json.dumps(options)
        context.preferences.is_dirty=True;tag_redraw(context)
        self.report({'INFO'},'Captured '+native.bl_label);return {'FINISHED'}


CLASSES=(BLAYA_OT_shelf_style,BLAYA_OT_capture_tool)
def register():
    ICONS.clear()
    for n,key in enumerate(bpy.types.UILayout.bl_rna.functions['operator'].parameters['icon'].enum_items.keys()):
        if key!='NONE':ICONS.append((key,key.replace('_',' ').title(),key,key,n))
    for cls in CLASSES:bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
    ICONS.clear()
