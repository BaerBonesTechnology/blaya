"""Run with --background --factory-startup --python-exit-code 1 --python."""
import bpy
import bmesh
import numpy as np
from blaya import loop_tools, circular
from blaya.mesh_preview import MeshPreview


def make_chain(points, closed=False):
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    mesh=bpy.data.meshes.new('Loop test')
    edges=[(i,i+1) for i in range(len(points)-1)]
    if closed: edges.append((len(points)-1,0))
    mesh.from_pydata(points,edges,[])
    obj=bpy.data.objects.new('Loop test',mesh)
    bpy.context.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bm=bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    return obj,bm


def coords(bm):
    return np.array([tuple(v.co) for v in bm.verts])

obj,bm=make_chain([(0,0,0),(.2,0,0),(1,0,0),(3,0,0)])
assert bpy.ops.blaya.space()=={'FINISHED'}
assert np.allclose(coords(bm)[:,0],[0,1,2,3])
obj,bm=make_chain([(0,0,0),(1,2,0),(2,-1,0),(3,0,0)])
original=coords(bm)
assert bpy.ops.blaya.straighten()=={'FINISHED'}
assert np.allclose(coords(bm)[:,1:],0)
assert np.allclose(coords(bm)[[0,-1]],original[[0,-1]])
obj,bm=make_chain(original)
assert bpy.ops.blaya.relax(iterations=1,influence=.5)=={'FINISHED'}
assert np.allclose(coords(bm)[[0,-1]],original[[0,-1]])
assert np.max(abs(coords(bm)[:,1])) < np.max(abs(original[:,1]))
obj,bm=make_chain([(0,0,0),(1,0,0),(1,1,0),(0,1,0)],closed=True)
original=coords(bm)
assert bpy.ops.blaya.straighten()=={'CANCELLED'}
assert np.allclose(coords(bm),original)
assert bpy.ops.blaya.space()=={'FINISHED'}
assert np.allclose(coords(bm),original)

# Exercise preview transaction with real edit meshes and the production solver.
class Preview(MeshPreview):
    calculate_changes=circular.BLAYA_OT_circularize.calculate_changes
    plane='BEST'
    center_mode='FIT'
    radius=2
    even=True
    flatten=True
    influence=1
    def report(self,*args): pass

obj,bm=make_chain([(2,0,0),(0,1,0),(-2,0,0),(0,-1,0)],closed=True)
original=coords(bm)
p=Preview()
p._snapshot=[(obj,[(v.index,v.co.copy()) for v in bm.verts])]
assert p.check(bpy.context)
first=coords(bm)
assert np.allclose(np.linalg.norm(first,axis=1),2)
p.radius=3
p.check(bpy.context)
assert np.allclose(np.linalg.norm(coords(bm),axis=1),3)
p.radius=2
p.check(bpy.context)
assert np.allclose(coords(bm),first), 'Preview must not accumulate'
p.cancel(bpy.context)
assert np.allclose(coords(bm),original), 'Cancel must restore exactly'
p._snapshot=[(obj,[(v.index,v.co.copy()) for v in bm.verts])]
p.check(bpy.context)
assert p.execute(bpy.context)=={'FINISHED'}
assert np.allclose(coords(bm),first), 'Apply must match preview'
# Invalid preview restores original instead of leaving stale geometry.
p._snapshot=[(obj,[(v.index,v.co.copy()) for v in bm.verts])]
baseline=coords(bm)
p.plane='X'
p.check(bpy.context)
assert p._preview_error and np.allclose(coords(bm),baseline)
p.cancel(bpy.context)
bpy.ops.object.mode_set(mode='OBJECT')
print('PASS: space, straighten, relax, fixed endpoints, closed-loop handling, preview recompute, apply, cancel and invalid preview restoration',flush=True)
