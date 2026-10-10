"""Read-only mesh inspection shared by the report and selection actions."""
RULES = (
    ('boundary', 'Open boundary edges', 'edges'),
    ('nonmanifold', 'Non-manifold edges', 'edges'),
    ('loose', 'Loose geometry vertices', 'vertices'),
    ('ngon', 'N-gons', 'faces'),
    ('degenerate', 'Small / zero-area faces', 'faces'),
)


def candidates(bm, rule, area_threshold):
    if rule == 'boundary':
        return [edge for edge in bm.edges if not edge.hide and edge.is_boundary]
    if rule == 'nonmanifold':
        return [edge for edge in bm.edges if not edge.hide and not edge.is_manifold]
    if rule == 'loose':
        return [vertex for vertex in bm.verts if not vertex.hide and not vertex.link_faces]
    if rule == 'ngon':
        return [face for face in bm.faces if not face.hide and len(face.verts) > 4]
    if rule == 'degenerate':
        return [face for face in bm.faces if not face.hide and face.calc_area() <= area_threshold]
    raise ValueError(f'Unknown cleanup rule: {rule}')


def counts(bm, area_threshold):
    return {rule: len(candidates(bm, rule, area_threshold)) for rule, _, _ in RULES}
