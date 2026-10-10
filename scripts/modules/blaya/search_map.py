"""Searchable learning catalog; deliberately independent of Blender's runtime."""
import re
from difflib import SequenceMatcher


def entry(key, maya, blender, aliases, where, note, command=None, mode='EDIT_MESH', editor='VIEW_3D'):
    return dict(id=key, maya=maya, blender=blender, aliases=aliases, where=where,
                note=note, command=command, mode=mode, editor=editor)


ENTRIES = [
    entry('relax', 'Relax', 'Relax Edge Chains / Loops', 'smooth relax vertices loop',
          'Kitchen 3D Tools > Model > Modeling Tools > Shape / Spacing > Relax',
          'Smooths selected chains or loops with live preview. Open endpoints stay fixed; closed loops may shrink.', 'relax'),
    entry('space', 'Evenly Space Vertices', 'Space', 'distribute uniform spacing vertices edge',
          'Kitchen 3D Tools > Model > Modeling Tools > Shape / Spacing > Space',
          'Redistributes vertices by distance along the original polyline. Endpoints stay fixed on open chains; corners may soften.', 'space'),
    entry('straighten', 'Straighten Vertices', 'Straighten', 'straight align vertices line',
          'Kitchen 3D Tools > Model > Modeling Tools > Shape / Spacing > Straighten',
          'Straightens an open chain between its endpoints. Closed loops must first be partially deselected.', 'straighten'),
    entry('circularize', 'Circularize', 'Circularize', 'round hole circle circular edge loop evenly space vertices',
          'Kitchen 3D Tools > Model > Modeling Tools > Shape / Spacing > Circularize',
          'Rounds selected closed loops or unconnected vertices without changing topology. Set radius to zero for automatic fit; choose even spacing, center and plane in the dialog.', 'circularize'),
    entry('freeze', 'Freeze Transformations', 'Apply Rotation & Scale',
          'freeze transforms reset transforms', 'Object Mode > Object > Apply > Rotation & Scale',
          'Related workflow, not identical. This action preserves location. Applying Location in Blender moves the origin to world zero. This action only runs on unanimated, unconstrained, single-user meshes without armature modifiers.', 'freeze', 'OBJECT'),
    entry('center', 'Center Pivot', 'Origin to Geometry', 'center pivot centre pivot',
          'Object Mode > Object > Set Origin > Origin to Geometry',
          'Moves the object origin to its geometry center. Blender also has temporary transform pivot choices; those are separate from the object origin.', 'origin_center', 'OBJECT'),
    entry('pivot', 'Edit / Move Pivot', 'Affect Only Origins', 'insert d pivot move origin',
          'Object Mode > 3D Viewport > Tool Settings > Options > Affect Only > Origins',
          'Use the transform tools to move the origin, then turn Origins off to move geometry again. Blender does not reproduce every Maya pivot behavior.', 'origin_edit', 'OBJECT'),
    entry('snap_pivot', 'Snap Pivot to Component', 'Cursor to Selected + Origin to 3D Cursor',
          'snap pivot vertex origin position', 'Edit Mode: snap Cursor to Selected; Object Mode: Object > Set Origin > Origin to 3D Cursor',
          'This is a two-step workflow. Place the cursor at selected components first, then return to Object Mode and set the origin. The run button performs only the final step.', 'origin_cursor', 'OBJECT'),
    entry('merge', 'Merge Vertices', 'Merge by Distance', 'weld merge vertices threshold',
          'Edit Mode > Mesh > Clean Up > Merge by Distance',
          'Merges selected vertices within a distance threshold. For a chosen collapse point, use Blender Merge at Center, First, or Last instead.', 'merge'),
    entry('cleanup', 'Cleanup: Nonmanifold Geometry', 'Select Non-Manifold / Inspection',
          'cleanup clean up nonmanifold non manifold mesh errors', 'Edit Mode > Select > Select All by Trait > Non-Manifold',
          'Selects visible non-manifold edges, including open boundaries and wires. This is inspection, not automatic repair; open borders may be intentional.', 'nonmanifold'),
    entry('ngons', 'Cleanup: Faces with More Than 4 Sides', 'Select Faces by Sides / N-gon Inspection',
          'cleanup ngons n-gons polygons five sides', 'Edit Mode > Select > Select All by Trait > Faces by Sides',
          'Selects visible faces with more than four vertices. N-gons may be acceptable depending on the modeling and export requirements.', 'ngon'),
    entry('extrude', 'Extrude', 'Extrude Region and Move', 'extrusion extrude faces',
          'Edit Mode > Mesh > Extrude > Extrude Region',
          'Runs region extrusion for the selection. Blender has separate individual-face extrusion and inset tools.', 'extrude'),
    entry('bevel', 'Bevel', 'Bevel', 'chamfer bevel edges', 'Edit Mode > Edge > Bevel Edges',
          'Runs a mesh edit on selected edges. Blender also offers a non-destructive Bevel modifier.', 'bevel'),
    entry('cut_uv', 'Cut UV Edges', 'Mark Seam, then Unwrap', 'cut uv shell seams',
          'Edit Mode > Edge > Mark Seam; then UV > Unwrap',
          'Mark Seam guides the next unwrap; it does not immediately cut existing UVs. Use UV Editor Split for an immediate UV separation. This button marks seams only.', 'seam'),
    entry('unfold', 'Unfold UVs', 'Unwrap', 'unfold unwrap uv shell',
          'Edit Mode > UV > Unwrap',
          'Unwrap selected faces using seams and pins. Maya Unfold and Blender Unwrap are related workflows with different algorithms and options.', 'unwrap'),
    entry('automatic', 'Automatic UV Mapping', 'Smart UV Project', 'automatic mapping projection uv',
          'Edit Mode > UV > Smart UV Project',
          'Creates projected UV islands based on face angles. Expect different cuts and packing from Maya Automatic Mapping.', 'smart_uv'),
    entry('layout', 'Layout UVs', 'Pack Islands', 'layout pack shells uv islands',
          'UV Editor > UV > Pack Islands',
          'Maya UV shells are called islands in Blender. Packing options control margins, rotation, and scale; select the UVs you want to pack.', 'pack_uv', editor='UV'),
    entry('density', 'Equalize Texel Density', 'Average Island Scale', 'texel density normalize uv scale shells',
          'UV Editor > UV > Average Island Scale',
          'Equalizes relative island scale based on surface area. It does not set an absolute pixels-per-unit target. Pack Islands afterward if needed.', 'average_uv', editor='UV'),
    entry('uv_orientation', 'Flipped / Mirrored UV Shells', 'UV Orientation',
          'flipped reversed backward mirrored uv shell winding red blue',
          'UV Editor > Sidebar > UV > UV Orientation > Show UV Orientation',
          'Blue indicates positive UV winding, red indicates mirrored winding, and yellow marks collapsed UV faces. Rotation is not mirroring. Colors classify individual faces, so a folded island can contain more than one color. Mirroring can be intentional.', editor='UV'),
    entry('uv_checker', 'UV Checker Map', 'Lettered Color Grid',
          'checker texture letters grid uv test pattern',
          'UV Editor > Sidebar > UV > UV Orientation > Show Lettered Checker',
          'Displays a labeled grid behind UVs in this editor. It does not assign a material or preview the grid on the 3D model. Use orientation colors to check mirrored UVs.', editor='UV'),
    entry('uv_sew', 'Sew UV Edges', 'Stitch', 'sew stitch weld uv borders',
          'UV Editor > UV > UV Finish > Sew',
          'Stitches matching UV edges using Blender’s native stitch interaction. Adjust the options and confirm the operation.', editor='UV'),
    entry('uv_density', 'Set Texel Density', 'Set Density', 'texel density pixels per meter resolution',
          'UV Editor > UV > UV Finish > Texture / px per meter > Set Density',
          'Scales fully selected islands to a pixels-per-meter target using world-space area and scene units. Partial islands are skipped. Disable Fit Tile when packing to retain the density.', editor='UV'),
    entry('group', 'Group Objects', 'Parent to Empty', 'group hierarchy organize outliner',
          '3D Viewport > Scene > Scene Tools > Group',
          'Creates an Empty and parents selected root objects to it while preserving their world transforms. Blender collections are a separate organization mechanism.', mode='OBJECT'),
    entry('isolate', 'Isolate Select', 'Local View', 'isolate solo selected object',
          '3D Viewport > Scene > Scene Tools > Isolate',
          'Toggles local view in this viewport. Run it again to return to the full scene.', mode='OBJECT'),
    entry('selection_sets', 'Quick Select Sets', 'Component Selection Sets', 'selection set save recall components',
          '3D Viewport > Model > Selection > Set / Save / Recall',
          'Stores named component selections on edited meshes. Recall refuses a missing set or changed topology rather than selecting unrelated components.'),
    entry('multi_cut', 'Multi-Cut', 'Knife / Bisect', 'multi cut split polygon slice plane knife',
          'Model > Modeling Tools > Cut / Connect > Knife',
          'Knife draws cuts interactively; Enter confirms and Esc cancels. Bisect slices selected geometry with a plane. These are separate Blender tools rather than one combined Maya tool.', 'knife'),
    entry('insert_loop', 'Insert Edge Loop', 'Loop Cut and Slide', 'insert edge loop split ring loopcut',
          'Model > Modeling Tools > Cut / Connect > Loop Cut',
          'Hover a quad strip, scroll for cut count, click to place, then slide. Triangles and n-gons can interrupt the loop.', 'loop_cut'),
    entry('connect', 'Connect Components', 'Connect Vertex Path', 'connect vertices components split face',
          'Model > Modeling Tools > Cut / Connect > Connect',
          'Select vertices across a connected face path. Blender splits the intervening faces; this is not a general bridge between disconnected pieces.', 'connect'),
    entry('bridge', 'Bridge', 'Bridge Edge Loops', 'bridge border edges loops',
          'Model > Modeling Tools > Cut / Connect > Bridge',
          'Select two open boundary loops. Matching vertex counts give predictable quads. Adjust twist and cuts in Adjust Last Operation.', 'bridge'),
    entry('grid_fill', 'Fill Hole / Quad Patch', 'Grid Fill', 'fill hole quad patch grid fill',
          'Model > Modeling Tools > Cut / Connect > Grid Fill',
          'Unlike a single polygon cap, Grid Fill attempts a quad patch. It needs suitable boundary topology, usually an even closed loop. Adjust span and offset if the patch twists.', 'grid_fill'),
    entry('slide', 'Slide Edge Tool', 'Edge Slide', 'slide edge slide edge loop',
          'Model > Modeling Tools > Edges > Slide',
          'Moves selected edges along neighboring topology; click to confirm or Esc to cancel.', 'edge_slide'),
    entry('dissolve', 'Delete Edge / Vertex', 'Dissolve', 'delete edge vertex dissolve remove edge retain face',
          'Model > Modeling Tools > Edges > Dissolve',
          'Dissolve removes selected components while retaining surrounding surfaces. It can create n-gons; inspect the result before subdivision or export.', 'dissolve'),
    entry('crease', 'Crease Tool', 'Edge Crease', 'crease subdivision hard edge',
          'Model > Modeling Tools > Edges > Crease',
          'Controls subdivision sharpness on selected edges. This is different from hard/soft shading normals; use a subdivision modifier to see the crease effect.', 'crease'),
    entry('mirror', 'Mirror Geometry', 'Mirror Modifier', 'mirror symmetry clipping merge axis',
          'Model > Modeling Tools > Symmetry > Mirror',
          'Adds a live X Mirror with clipping and merge, or exposes the first existing Mirror without changing it. Start with a half mesh and position the origin at the mirror plane. This does not delete a half or apply the modifier.', 'mirror', 'OBJECT'),
    entry('symmetrize', 'Symmetrize', 'Symmetrize', 'symmetrize symmetry copy side',
          'Model > Modeling Tools > Symmetry > Symmetrize',
          'Choose the source-to-destination local axis before confirming. Changes selected mesh geometry; this is a one-time topology operation rather than a live Mirror modifier.', 'symmetrize'),
    entry('face_normals', 'Reverse Normals / Face Orientation', 'Flip Normals / Face Orientation', 'reverse normals flip face red blue backface',
          'Model > Modeling Tools > Normals',
          'Flip reverses selected faces. Face Orientation displays front faces blue and back faces red, separately from UV winding. Recalculate attempts consistent outward normals and is most reliable on closed surfaces.', 'flip_normals'),
    entry('soft_selection', 'Soft Selection', 'Proportional Editing', 'soft selection falloff radius connected projected',
          'Model > Pivot > Soft Selection',
          'Enable proportional editing, choose a falloff and start a transform. Scroll changes radius. Connected limits influence to connected geometry; object-level proportional editing is a separate toggle.'),
    entry('hard_soft_edges', 'Harden / Soften Edge', 'Sharp Edges + Smooth Faces', 'hard soft edge normals shading soften harden',
          'Model > Modeling Tools > Normals > Hard / Soft',
          'Hard marks selected visible edges sharp; Soft clears sharpness. Both smooth adjacent visible faces so edge shading can take effect. Existing custom normals or modifiers can alter the final appearance.'),
    entry('constraints', 'Transform Axis Constraints', 'Constrained Move / Rotate / Scale', 'axis plane constraint snap move rotate scale x y z',
          'Model > Pivot > Transform Constraints',
          'Choose Move, Rotate or Scale and click an axis. During native transforms, X/Y/Z locks an axis; Shift-X/Y/Z excludes one. Snap With controls the selection reference point.'),
    entry('history', 'Delete History', 'No Single Direct Equivalent', 'delete construction history bake modifiers',
          'Inspect the object Modifier stack; apply individual modifiers when appropriate',
          'Blender does not maintain Maya-style construction history. Applying a modifier bakes that modifier into geometry; do not blindly apply all modifiers to imitate Delete History.', mode='OBJECT'),
]
BY_ID = {item['id']: item for item in ENTRIES}


def normalize(text):
    return ' '.join(re.findall(r'[a-z0-9]+', text.casefold()))


def search(query, entries=None):
    """Rank exact/prefix/word matches first, then conservative typo matches."""
    entries = ENTRIES if entries is None else entries
    query = normalize(query)
    if not query:
        return list(entries)
    ranked = []
    for index, item in enumerate(entries):
        maya = normalize(item['maya'])
        title = normalize(item['maya'] + ' ' + item['blender'] + ' ' + item['aliases'])
        words = title.split()
        tokens = query.split()
        if all(token in title for token in tokens):
            score = 100 + (40 if query == maya else 20 if maya.startswith(query) else 0)
        elif all(any(SequenceMatcher(None, token, word).ratio() >= 0.78 for word in words) for token in tokens):
            score = 30 + 20 * sum(max(SequenceMatcher(None, token, word).ratio()
                                       for word in words) for token in tokens) / len(tokens)
            score += 10 * SequenceMatcher(None, query, maya).ratio()
        else:
            continue
        ranked.append((-score, index, item))
    return [item for _, _, item in sorted(ranked)]
