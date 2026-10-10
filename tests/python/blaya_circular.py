"""Kitchen 3D --background --factory-startup --python-exit-code 1 --python this_file."""
import math
import numpy as np
import bpy
import bmesh
from blaya.circular import circle_points

angles = np.array([0, .3, 1.4, 2.1, 3.2, 4.7, 5.5])
points = np.column_stack((2+3*np.cos(angles), -1+3*np.sin(angles), np.full(7, 4)))
result = circle_points(points, even=False)
assert np.allclose(result, points), 'Uneven samples of an existing circle should stay put'
result = circle_points(points, radius=2, even=True)
assert np.allclose(np.linalg.norm(result-[2,-1,4], axis=1), 2)
assert np.allclose(np.linalg.norm(np.roll(result, -1, axis=0)-result, axis=1), 4*math.sin(math.pi/7))
assert np.allclose(circle_points(points, radius=2, influence=0), points)
raised = points.copy()
raised[:, 2] += np.sin(angles)*.2
result = circle_points(raised, plane='Z', center_mode='CURSOR', cursor=(2,-1,0), flatten=False)
assert np.allclose(result[:,2], raised[:,2])
result = circle_points(raised, plane='Z', center_mode='CURSOR', cursor=(2,-1,0), flatten=True)
assert np.allclose(result[:,2], 0)

# Round a hole in a quad annulus with a rotated, nonuniformly scaled object.
bpy.ops.object.select_all(action='DESELECT')
verts = [(r*math.cos(i*math.tau/8), r*.7*math.sin(i*math.tau/8), 0)
         for r in (1,3) for i in range(8)]
faces = [(i, (i+1)%8, (i+1)%8+8, i+8) for i in range(8)]
mesh = bpy.data.meshes.new('Quad hole')
mesh.from_pydata(verts, [], faces)
obj = bpy.data.objects.new('Quad hole', mesh)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
obj.scale = (2, 1, .6)
obj.rotation_euler = (.3, .4, .2)
bpy.context.view_layer.update()
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(mesh)
bm.verts.ensure_lookup_table()
for face in bm.faces: face.select_set(False)
for edge in bm.edges: edge.select_set(False)
for vertex in bm.verts: vertex.select_set(vertex.index < 8)
bm.select_flush_mode()
outer = [v.co.copy() for v in bm.verts if v.index >= 8]
counts = (len(bm.verts), len(bm.edges), len(bm.faces))
assert bpy.ops.blaya.circularize(radius=1.5) == {'FINISHED'}
world = np.array([tuple(obj.matrix_world @ bm.verts[i].co) for i in range(8)])
assert np.allclose(np.linalg.norm(world-world.mean(axis=0), axis=1), 1.5, atol=1e-5)
assert all((v.co-co).length < 1e-6 for v,co in zip(list(bm.verts)[8:],outer))
assert counts == (len(bm.verts),len(bm.edges),len(bm.faces)) and all(len(f.verts)==4 for f in bm.faces)
# Invalid branched selection must not partially change the mesh.
for vertex in bm.verts: vertex.select_set(True)
bm.select_flush_mode()
before = [v.co.copy() for v in bm.verts]
assert bpy.ops.blaya.circularize() == {'CANCELLED'}
assert all((v.co-co).length < 1e-6 for v,co in zip(bm.verts,before))
bpy.ops.object.mode_set(mode='OBJECT')
# Two independent loops are fit independently.
bpy.ops.object.select_all(action='DESELECT')
verts = [(cx+2*math.cos(i*math.tau/6), math.sin(i*math.tau/6), 0) for cx in (-4,4) for i in range(6)]
edges = [(base+i,base+(i+1)%6) for base in (0,6) for i in range(6)]
mesh = bpy.data.meshes.new('Two loops')
mesh.from_pydata(verts,edges,[])
obj = bpy.data.objects.new('Two loops',mesh)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
assert bpy.ops.blaya.circularize(radius=1) == {'FINISHED'}
bm = bmesh.from_edit_mesh(mesh)
bm.verts.ensure_lookup_table()
for base,cx in ((0,-4),(6,4)):
    coords = np.array([tuple(bm.verts[base+i].co) for i in range(6)])
    assert np.allclose(coords.mean(axis=0),(cx,0,0),atol=1e-5)
    assert np.allclose(np.linalg.norm(coords-(cx,0,0),axis=1),1,atol=1e-5)
bpy.ops.object.mode_set(mode='OBJECT')
print('PASS: fitted circle, even spacing, radius, depth, influence, quad-hole topology, world scale, separate loops and atomic rejection',flush=True)
