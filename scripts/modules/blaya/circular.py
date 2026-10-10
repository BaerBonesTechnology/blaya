"""Topology-preserving circularization in world space."""
import math
from .mesh_preview import MeshPreview
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty


def selected_groups(bm):
    verts = {v for v in bm.verts if v.select and not v.hide}
    if len(verts) < 3:
        raise ValueError('Select at least three vertices')
    adjacent = {v: [e.other_vert(v) for e in v.link_edges
                    if not e.hide and e.other_vert(v) in verts] for v in verts}
    if all(not neighbors for neighbors in adjacent.values()):
        return [(sorted(verts, key=lambda v: v.index), False)]
    if any(len(neighbors) != 2 for neighbors in adjacent.values()):
        raise ValueError('Select closed edge loops, or unconnected vertices; exclude branches and interior vertices')
    groups = []
    remaining = set(verts)
    while remaining:
        first = min(remaining, key=lambda v: v.index)
        ordered = [first]
        previous, current = first, min(adjacent[first], key=lambda v: v.index)
        while current != first:
            ordered.append(current)
            neighbors = adjacent[current]
            previous, current = current, next(v for v in neighbors if v != previous)
        remaining.difference_update(ordered)
        groups.append((ordered, True))
    return groups


def circle_points(points, *, plane='BEST', center_mode='FIT', cursor=(0, 0, 0),
                  radius=0, even=True, flatten=True, influence=1, closed=True):
    points = np.asarray(points, dtype=float)
    center = points.mean(axis=0)
    relative = points - center
    values, vectors = np.linalg.eigh(relative.T @ relative)
    if values[1] <= max(values[2] * 1e-10, 1e-20):
        raise ValueError('The selection is collinear or too small to define a circle')
    normal = vectors[:, 0] if plane == 'BEST' else np.eye(3)['XYZ'.index(plane)]
    if normal[np.argmax(abs(normal))] < 0:
        normal = -normal
    axis = np.eye(3)[np.argmin(abs(normal))]
    u = np.cross(normal, axis)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    if center_mode == 'CURSOR':
        center = np.asarray(cursor, dtype=float)
    elif center_mode == 'FIT':
        x, y = relative @ u, relative @ v
        design = np.column_stack((2*x, 2*y, np.ones(len(points))))
        fitted, _, rank, _ = np.linalg.lstsq(design, x*x+y*y, rcond=None)
        if rank < 3:
            raise ValueError('The chosen plane collapses the selection; choose Best Fit or another axis')
        center += u*fitted[0] + v*fitted[1]
    relative = points - center
    x, y = relative @ u, relative @ v
    lengths = np.hypot(x, y)
    if min(lengths) <= max(max(lengths)*1e-10, 1e-12):
        raise ValueError('A selected vertex lies at the circle center; choose another center or plane')
    target_radius = radius if radius > 0 else float(np.mean(lengths))
    angles = np.arctan2(y, x)
    if even:
        order = np.arange(len(points)) if closed else np.argsort(angles)
        ordered_angles = angles[order]
        winding = np.sum(x[order] * np.roll(y[order], -1) - y[order] * np.roll(x[order], -1))
        direction = 1 if winding >= 0 else -1
        offsets = direction * np.arange(len(points)) * (2*math.pi/len(points))
        phase = np.angle(np.mean(np.exp(1j*(ordered_angles-offsets))))
        angles[order] = phase + offsets
    result = center + target_radius * (np.cos(angles)[:, None]*u + np.sin(angles)[:, None]*v)
    if not flatten:
        result += (relative @ normal)[:, None]*normal
    return points + influence*(result-points)


class BLAYA_OT_circularize(MeshPreview, bpy.types.Operator):
    bl_idname = 'blaya.circularize'
    bl_label = 'Circularize'
    bl_description = 'Round selected closed edge loops or unconnected vertices without changing topology; separate loops get separate circles'
    bl_options = {'REGISTER', 'UNDO'}
    plane: EnumProperty(name='Plane', items=[
        ('BEST', 'Best Fit', 'Fit a plane to each loop'),
        ('X', 'World YZ', 'Circle perpendicular to world X'),
        ('Y', 'World XZ', 'Circle perpendicular to world Y'),
        ('Z', 'World XY', 'Circle perpendicular to world Z')], default='BEST')
    center_mode: EnumProperty(name='Center', items=[
        ('FIT', 'Best Fit', 'Fit a circle center to the projected vertices'),
        ('MEDIAN', 'Selection Center', 'Use the average position of each loop'),
        ('CURSOR', '3D Cursor', 'Use the 3D Cursor as a shared world-space center')], default='FIT')
    radius: FloatProperty(name='Radius', default=0, min=0, subtype='DISTANCE', unit='LENGTH',
                          description='World-space radius; zero fits a radius to each loop')
    even: BoolProperty(name='Even Spacing', default=True,
                       description='Space vertices equally around each circle, preserving loop connectivity')
    flatten: BoolProperty(name='Flatten', default=True,
                          description='Place vertices on the circle plane; disable to preserve their depth')
    influence: FloatProperty(name='Influence', default=1, min=0, max=1, subtype='FACTOR',
                             description='Blend between the original shape and the circle')

    def draw(self, context):
        for name in ('plane', 'center_mode', 'radius', 'even', 'flatten', 'influence'):
            self.layout.prop(self, name)
        self.draw_error()

    def calculate_changes(self, context):
        changes = []
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.index_update()
            if not any(v.select and not v.hide for v in bm.verts):
                continue
            if abs(obj.matrix_world.determinant()) < 1e-12:
                raise ValueError('An edited object has zero scale; restore its scale first')
            inverse = obj.matrix_world.inverted()
            for verts, closed in selected_groups(bm):
                result = circle_points([tuple(obj.matrix_world @ vert.co) for vert in verts],
                                       plane=self.plane, center_mode=self.center_mode,
                                       cursor=tuple(context.scene.cursor.location), radius=self.radius,
                                       even=self.even, flatten=self.flatten, influence=self.influence,
                                       closed=closed)
                changes.append((obj, bm, verts, [inverse @ Vector(co) for co in result]))
        return changes


def register():
    bpy.utils.register_class(BLAYA_OT_circularize)


def unregister():
    bpy.utils.unregister_class(BLAYA_OT_circularize)
