"""Topology-preserving tools for open chains and closed loops."""
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from bpy.props import FloatProperty, IntProperty
from .mesh_preview import MeshPreview


def chains(bm):
    selected = {v for v in bm.verts if v.select and not v.hide}
    neighbors = {v: [e.other_vert(v) for e in v.link_edges if not e.hide and e.other_vert(v) in selected]
                 for v in selected}
    if any(len(n) > 2 or not n for n in neighbors.values()):
        raise ValueError('Select connected edge chains or loops without branches')
    remaining = set(selected)
    groups = []
    while remaining:
        # Find one component before choosing an endpoint.
        component, pending = set(), [min(remaining, key=lambda v: v.index)]
        while pending:
            vertex = pending.pop()
            if vertex in component:
                continue
            component.add(vertex)
            pending.extend(n for n in neighbors[vertex] if n not in component)
        if len(component) < 3:
            raise ValueError('Each chain or loop needs at least three vertices')
        ends = [v for v in component if len(neighbors[v]) == 1]
        closed = not ends
        first = min(ends or component, key=lambda v: v.index)
        ordered = [first]
        previous, current = None, first
        while True:
            candidates = [v for v in neighbors[current] if v != previous and v != first]
            if not candidates:
                break
            following = min(candidates, key=lambda v: v.index)
            ordered.append(following)
            previous, current = current, following
        remaining.difference_update(component)
        groups.append((ordered, closed))
    return groups


def spaced(points, closed):
    path = np.vstack((points, points[0])) if closed else points
    lengths = np.linalg.norm(np.diff(path, axis=0), axis=1)
    cumulative = np.concatenate(([0], np.cumsum(lengths)))
    if cumulative[-1] <= 1e-12:
        raise ValueError('The selected path has no length')
    # Remove repeated points for unambiguous interpolation.
    keep = np.concatenate(([True], lengths > 1e-12))
    positions = np.linspace(0, cumulative[-1], len(points), endpoint=not closed)
    return np.column_stack([np.interp(positions, cumulative[keep], path[keep, axis]) for axis in range(3)])


class LoopTool(MeshPreview):
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
            for vertices, closed in chains(bm):
                points = np.array([tuple(obj.matrix_world @ v.co) for v in vertices])
                result = self.transform_points(points, closed)
                changes.append((obj, bm, vertices, [inverse @ Vector(co) for co in result]))
        return changes


class BLAYA_OT_relax(LoopTool, bpy.types.Operator):
    bl_idname = 'blaya.relax'
    bl_label = 'Relax'
    bl_description = 'Smooth selected edge chains or loops; open endpoints stay fixed. Closed loops can shrink'
    bl_options = {'REGISTER', 'UNDO'}
    influence: FloatProperty(name='Strength', default=.5, min=0, max=1, subtype='FACTOR')
    iterations: IntProperty(name='Iterations', default=3, min=1, max=100)

    def transform_points(self, points, closed):
        result = points.copy()
        for _ in range(self.iterations):
            average = (np.roll(result, 1, axis=0)+np.roll(result, -1, axis=0))*.5
            if not closed:
                average[0], average[-1] = result[0], result[-1]
            result += self.influence*(average-result)
        return result

    def draw(self, context):
        self.layout.prop(self, 'influence')
        self.layout.prop(self, 'iterations')
        self.draw_error()


class BLAYA_OT_space(LoopTool, bpy.types.Operator):
    bl_idname = 'blaya.space'
    bl_label = 'Space'
    bl_description = 'Space vertices equally along the original selected polyline; open endpoints stay fixed. Corners may soften'
    bl_options = {'REGISTER', 'UNDO'}
    influence: FloatProperty(name='Influence', default=1, min=0, max=1, subtype='FACTOR')

    def transform_points(self, points, closed):
        return points+self.influence*(spaced(points, closed)-points)

    def draw(self, context):
        self.layout.prop(self, 'influence')
        self.draw_error()


class BLAYA_OT_straighten(LoopTool, bpy.types.Operator):
    bl_idname = 'blaya.straighten'
    bl_label = 'Straighten'
    bl_description = 'Straighten an open edge chain between its fixed endpoints, retaining proportional distances along the original path'
    bl_options = {'REGISTER', 'UNDO'}
    influence: FloatProperty(name='Influence', default=1, min=0, max=1, subtype='FACTOR')

    def transform_points(self, points, closed):
        if closed:
            raise ValueError('Straighten needs an open chain; deselect part of the loop')
        lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
        if sum(lengths) <= 1e-12 or np.linalg.norm(points[-1]-points[0]) <= 1e-12:
            raise ValueError('The chain needs distinct endpoints')
        t = np.concatenate(([0], np.cumsum(lengths)))/sum(lengths)
        target = points[0]+t[:,None]*(points[-1]-points[0])
        return points+self.influence*(target-points)

    def draw(self, context):
        self.layout.prop(self, 'influence')
        self.draw_error()


CLASSES = (BLAYA_OT_relax, BLAYA_OT_space, BLAYA_OT_straighten)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
