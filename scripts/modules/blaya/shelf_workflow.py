"""Named shelves, registered Blender operators, portable JSON, keymap inspection."""
import bpy,json,re
from pathlib import Path
from bpy.props import StringProperty,EnumProperty
OP_ITEMS=[]


def operator_items(self,context):
    return OP_ITEMS


def metadata(command,context=None):
    from . import prefs,COMMANDS
    for key,label,group in COMMANDS:
        if key==command:return label,group
    settings=prefs(context)
    if settings:
        item=next((i for i in settings.shelf if i.command==command and i.shelf_name==settings.shelf_name),None)
        if item:return item.label or command.removeprefix('op:'),item.workflow
    return command,'Model'


class BLAYA_OT_custom_add(bpy.types.Operator):
    bl_idname='blaya.custom_add';bl_label='Add Blender Tool';bl_description='Search registered Blender operators and add one to the current shelf; runs with its default options'
    bl_property='operator_id'
    operator_id:EnumProperty(items=operator_items)
    workflow:StringProperty(default='Model')
    def invoke(self,context,event):
        OP_ITEMS.clear()
        for module in dir(bpy.ops):
            if module.startswith('_'):continue
            for name in dir(getattr(bpy.ops,module)):
                if name.startswith('_') or module=='blaya':continue
                op=getattr(getattr(bpy.ops,module),name)
                try:
                    rna=op.get_rna_type()
                    OP_ITEMS.append((f'{module}.{name}', f'{rna.name} — {module}.{name}', rna.description or rna.name))
                except (KeyError,RuntimeError):continue
        context.window_manager.invoke_search_popup(self);return {'FINISHED'}
    def execute(self,context):
        from . import prefs,tag_redraw
        settings=prefs(context);command='op:'+self.operator_id
        if any(i.command==command and i.shelf_name==settings.shelf_name for i in settings.shelf):return {'FINISHED'}
        item=settings.shelf.add();item.command=command;item.shelf_name=settings.shelf_name;item.workflow=self.workflow
        item.label=next((label.split(' — ')[0] for key,label,_ in OP_ITEMS if key==self.operator_id),self.operator_id)
        context.preferences.is_dirty=True;tag_redraw(context);return {'FINISHED'}


class BLAYA_OT_custom_run(bpy.types.Operator):
    bl_idname='blaya.custom_run';bl_label='Blender Tool';bl_options={'REGISTER','UNDO'}
    operator_id:StringProperty()
    @classmethod
    def description(cls,context,properties):
        try:
            module,name=properties.operator_id.split('.')
            rna=getattr(getattr(bpy.ops,module),name).get_rna_type()
            return rna.name+' — '+rna.description
        except (ValueError,AttributeError,KeyError):return properties.operator_id
    def execute(self,context):
        if not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',self.operator_id):return {'CANCELLED'}
        module,name=self.operator_id.split('.')
        try:
            op=getattr(getattr(bpy.ops,module),name)
            if not op.poll():self.report({'WARNING'},'Tool unavailable in this editor, mode or selection');return {'CANCELLED'}
            from .shelf_presets import item_for,validate_options
            item=item_for('op:'+self.operator_id,context)
            values=json.loads(item.options) if item else {}
            result=op('INVOKE_DEFAULT',**validate_options(self.operator_id,values))
            return {'FINISHED'} if 'RUNNING_MODAL' in result else result
        except (AttributeError,KeyError,RuntimeError,ValueError,TypeError) as error:self.report({'WARNING'},str(error));return {'CANCELLED'}


def shelf_payload(settings):
    return {'schema':2,'shelves':[{'command':i.command,'name':i.shelf_name,'label':i.label,'workflow':i.workflow,'icon':i.icon,'options':json.loads(i.options)} for i in settings.shelf]}


def validate_payload(data):
    from . import LABELS
    if not isinstance(data,dict) or data.get('schema') not in {1,2} or not isinstance(data.get('shelves'),list) or len(data['shelves'])>500:
        raise ValueError('Unsupported shelf file')
    records=[]
    for item in data['shelves']:
        if not isinstance(item,dict):raise ValueError('Invalid shelf entry')
        command=item.get('command');name=item.get('name');label=item.get('label','');workflow=item.get('workflow','Model')
        if not all(isinstance(v,str) and len(v)<=256 for v in (command,name,label,workflow)):raise ValueError('Invalid shelf fields')
        if not name.strip() or workflow not in {'Model','UV'}:raise ValueError('Invalid shelf name or workflow')
        if command not in LABELS and not re.fullmatch(r'op:[a-z_]+\.[a-z0-9_]+',command):raise ValueError('Unknown tool')
        icon=item.get('icon','');options=item.get('options',{})
        icons=bpy.types.UILayout.bl_rna.functions['operator'].parameters['icon'].enum_items.keys()
        if not isinstance(icon,str) or (icon and icon not in icons):raise ValueError('Unknown shelf symbol')
        if not isinstance(options,dict) or len(json.dumps(options))>64000:raise ValueError('Invalid tool options')
        if options and not command.startswith('op:'):raise ValueError('Options require a native tool')
        records.append((command,name,label,workflow,icon,json.dumps(options)))
    return records


class BLAYA_OT_shelf_file(bpy.types.Operator):
    bl_idname='blaya.shelf_file';bl_label='Shelf File'
    filepath:StringProperty(subtype='FILE_PATH')
    filter_glob:StringProperty(default='*.json',options={'HIDDEN'})
    action:EnumProperty(items=[('EXPORT','Export','Export all named shelves to JSON'),('IMPORT','Import','Merge shelves from JSON; tools do not run during import')])
    def invoke(self,context,event):
        if self.action=='EXPORT' and not self.filepath:self.filepath='blaya_shelves.json'
        context.window_manager.fileselect_add(self);return {'RUNNING_MODAL'}
    def execute(self,context):
        from . import prefs,tag_redraw
        settings=prefs(context)
        try:
            path=Path(self.filepath)
            if self.action=='EXPORT':
                path.write_text(json.dumps(shelf_payload(settings),indent=2))
            else:
                if path.stat().st_size>2_000_000:raise ValueError('Shelf file too large')
                records=validate_payload(json.loads(path.read_text()))
                existing={(i.command,i.shelf_name) for i in settings.shelf}
                for command,name,label,workflow,icon,options in records:
                    if (command,name) in existing:continue
                    item=settings.shelf.add();item.command=command;item.shelf_name=name;item.label=label;item.workflow=workflow;item.icon=icon;item.options=options
                    existing.add((command,name))
                context.preferences.is_dirty=True;tag_redraw(context)
            self.report({'INFO'},'Shelves '+('exported' if self.action=='EXPORT' else 'imported'));return {'FINISHED'}
        except (OSError,ValueError,TypeError) as error:self.report({'WARNING'},str(error));return {'CANCELLED'}


def event_signature(item):
    return (item.type,item.value,item.shift,item.ctrl,item.alt,item.oskey,item.key_modifier,item.any)


def matching_user_item(context, addon_km, item):
    km=context.window_manager.keyconfigs.user.keymaps.get(addon_km.name)
    if not km:return None,None
    props={key:getattr(item.properties,key) for key in item.properties.keys()}
    match=next((k for k in km.keymap_items if k.idname==item.idname and all(getattr(k.properties,key,None)==value for key,value in props.items())),None)
    return km,match


def events_overlap(a,b):
    if a.type!=b.type or (a.value!=b.value and 'ANY' not in {a.value,b.value}):return False
    if a.key_modifier!=b.key_modifier:return False
    return a.any or b.any or all(getattr(a,n)==getattr(b,n) or -1 in {getattr(a,n),getattr(b,n)} for n in ('shift','ctrl','alt','oskey'))


class BLAYA_OT_keymap_conflicts(bpy.types.Operator):
    bl_idname='blaya.keymap_conflicts';bl_label='Check Shortcuts'
    bl_description='Inspect edited user bindings against relevant editor, mode, tool and global bindings, including wildcard modifiers. Results are potential collisions; modal tools and other add-ons can still affect priority'
    def execute(self,context):
        from . import KEYMAPS
        conflicts=set();configs=context.window_manager.keyconfigs
        for addon_km,original in KEYMAPS:
            km,item=matching_user_item(context,addon_km,original)
            if not item or not item.active:continue
            scopes={'Window','Screen','Frames',addon_km.name}
            if addon_km.name in {'3D View','Object Mode','Mesh'}:scopes|={'3D View','3D View Generic','Object Mode','Mesh'}
            else:scopes|={'Image','Image Generic','UV Editor'}
            for base in configs.user.keymaps:
                relevant=base.name in scopes or (base.name.startswith('3D View Tool:') if '3D View' in scopes else base.name.startswith('Image Editor Tool:'))
                if not relevant or base.is_modal:continue
                for other in base.keymap_items:
                    if not other.active or (base==km and other.id==item.id):continue
                    if other.idname==item.idname and {k:repr(getattr(other.properties,k)) for k in other.properties.keys()}=={k:repr(getattr(item.properties,k)) for k in item.properties.keys()}:continue
                    if events_overlap(item,other):conflicts.add(f'{km.name}: {item.type} → {item.name} / {base.name}: {other.name}')
        context.window_manager.blaya_keymap_report=json.dumps(sorted(conflicts))
        self.report({'INFO'},f'{len(conflicts)} potential shortcut collisions');return {'FINISHED'}


class BLAYA_PT_shortcuts(bpy.types.Panel):
    bl_idname='BLAYA_PT_shortcuts';bl_label='Shortcuts';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Setup';bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        import rna_keymap_ui
        from . import KEYMAPS,prefs
        l=self.layout;l.prop(prefs(context),'space_menu')
        l.operator('blaya.keymap_conflicts',text='Check',icon='VIEWZOOM')
        report=json.loads(context.window_manager.blaya_keymap_report or '[]')
        if report:
            from . import hint
            row=l.row();row.label(text=f'{len(report)} potential conflicts');hint(row,'\n'.join(report))
        kc=context.window_manager.keyconfigs.user
        for addon_km,item in KEYMAPS:
            km=kc.keymaps.get(addon_km.name)
            if not km:continue
            # Match operator properties rather than event keys so edited keys stay findable.
            properties={key:getattr(item.properties,key) for key in item.properties.keys()}
            match=next((k for k in km.keymap_items if k.idname==item.idname and all(getattr(k.properties,key,None)==value for key,value in properties.items())),None)
            if match:
                rna_keymap_ui.draw_kmi([],kc,km,match,l,0)


CLASSES=(BLAYA_OT_custom_add,BLAYA_OT_custom_run,BLAYA_OT_shelf_file,BLAYA_OT_keymap_conflicts,BLAYA_PT_shortcuts)
def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.WindowManager.blaya_keymap_report=StringProperty(options={'SKIP_SAVE'})
def unregister():
    del bpy.types.WindowManager.blaya_keymap_report
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
