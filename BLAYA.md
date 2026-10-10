# Kitchen 3D | Blender Distro

Kitchen 3D helps artists coming from Maya feel at home in Blender. It is an independent
customized Blender distribution, not affiliated with or endorsed by the Blender
Foundation. Blender's authors, credits and license notices remain intact.

- [Support Blender development](https://fund.blender.org/)
- [Download official Blender](https://www.blender.org/download/)
- [Blender documentation](https://docs.blender.org/manual/en/latest/)

Kitchen 3D Lite is the separately installable add-on for official Blender. This fork
bundles its workflow implementation in `scripts/modules/blaya`; the native
entry point is `scripts/startup/blaya_framework.py`. The initial bundle is based
on Lite 0.9.0. Keep general workflow changes portable and consider contributing
broadly useful improvements upstream.

## First native integration

On a fresh Mac profile, Kitchen 3D registers its native workflows, chooses Industry
Compatible and opens a workspace with a dedicated, resizable Kitchen 3D Tools editor
on the left, a modeling viewport, UV editor, and the standard Properties editor
on the right. Saved .blend files retain their
own workspaces. Save Preferences to retain later keymap and shelf choices.
The Kitchen 3D menu exposes workspace setup, About, official Blender downloads,
documentation and Development Fund links.

Mac app identity: `Kitchen 3D.app`, bundle ID `com.baerbonestechnology.blaya`.
Mac preferences: `~/Library/Application Support/Blaya/5.3`, separate from Blender.
The file format and Python version tuple follow the Blender 5.3 release branch
(currently marked beta). The
underlying CLI version and upstream About/credits still identify Blender.
Other platforms have not yet received distinct packaging/preferences paths.

This is an initial developer build. Kitchen 3D uses teal rounded stove linework, with visible top and side faces and a small oven window. The canonical vector
is `release/branding/kitchen3d-mark.svg`; the macOS Icon Composer source is
`release/darwin/blaya.icon`. Run `release/darwin/build_blaya_icon.sh` with Xcode
to regenerate the modern asset catalog and legacy icon. Native 3D onion-skin
mesh overlays are available in the Animation workflow.

## Validation history on macOS ARM64

The runtime checks below describe the original Blender 5.2.2 integration.
The Blender 5.3 upgrade requires a fresh build and runtime validation.

The native GUI smoke test covers bundled tools, isolated preferences, Industry
Compatible defaults, the native tools editor, the Kitchen 3D menu and About popup, and
preservation of an existing file’s workspace. A background smoke test also
verified evaluated bevel geometry and a Cycles CPU render. Full C++ tests were
not run.

Native workflows register through startup code, independently of add-on discovery.
Settings live in Preferences → Interface → Kitchen 3D Workflow, backed by native
user-preference storage. The first developer build’s add-on settings migrate
automatically, including custom shelves. Kitchen 3D Lite remains a separate product
for official Blender.

## Native tools editor

Choose **Kitchen 3D Tools** from any area's editor selector. Its vertical workflow
rail provides Model, UV, Sculpt, Animation, Scene and Setup. Existing Kitchen 3D sidebar tools now live
in this editor; operators route to the largest matching modeling or UV view in
the same window. Icon grids use consistent square buttons, wrap to available
width and account for UI scaling. Icons + Text and Text remain available in Setup.
The Learning Map stays collapsed by default.

For an earlier Kitchen 3D workspace, use **Kitchen 3D → Open Kitchen 3D Workspace** to add the
native tools editor. Opening a saved file does not automatically rearrange it.
Settings migrate from the first bundled-add-on developer build into native
preferences, including named shelves and custom tool options.

Additional checks passed for preferences save/reload and factory reset, the
native Preferences panel, all workflow panel draws, modeling/UV operator routing,
legacy workspace upgrade, and wide/narrow icon layouts. Regression scripts live
under `tests/python/blaya_native*.py` and require an isolated user configuration.

## Animation workflow

Use **Kitchen 3D → Open Animation Workspace**, or the workspace button in the
Animation tab. The layout includes Kitchen 3D Tools, a viewport, Dope Sheet, Graph
Editor, Timeline and normal Properties. Reopening it preserves its arrangement.

- Set or delete current-frame Translate, Rotate, Scale or combined keys on
  selected objects or pose bones. Locked transform components are skipped.
- Toggle Auto Key, navigate frames/keys, and set playback or preview ranges.
- Move selected Dope Sheet keys earlier/later, or scale their timing around
  the current frame. Unselected keys and locked channels are preserved.
- Set selected Graph Editor keys to Stepped, Linear or Bézier interpolation;
  choose Auto Clamped, Auto, Vector, Aligned or Free handles.

Descriptions remain in hover tooltips. Timing and curve tools require their
matching animation editors in the same window. No animation hotkeys are
reassigned by this first pass.

`tests/python/blaya_animation_smoke.py` checks the rendered panels, workspace
reuse, object keying/deletion, selected-key timing, locked channels and curves.
`tests/python/blaya_animation_pose.py` checks selected pose bones, quaternion
rotation channels, component locks and current-frame key deletion.

## 3D onion skinning

In **Kitchen 3D Tools → Animation → Onion Skin**, select mesh objects (or a rig with
visible mesh objects) and enable **Onion Skin**. Earlier poses are **pink**;
later poses are **green** by default. Click the color swatch beneath Before or
After to choose a different color; changes appear immediately and colors save
with the scene. Before/After set the number of poses, Spacing sets
the frame interval, and Opacity controls transparency. Distant poses fade.
Samples stay within the scene playback range.

The overlay evaluates mesh modifiers and armature deformation in world space.
It follows the captured source objects until toggled off; toggle off/on to
capture a different selection. It refreshes after scrubbing settles. Use
**Refresh Ghosts** after changing animation or geometry at the same frame.
Ghosts hide during playback and when viewport overlays are disabled.

Ghosts are session-only GPU overlays: they add no objects, materials or mesh
datablocks, are not rendered, and are not stored in saved files. Loading a file
or undoing/redoing clears them. The exact frame and subframe are restored after
sampling, including on failure. A one-million-triangle aggregate sampling limit
prevents large ghost caches; reduce pose counts or geometry when needed.

This first version supports mesh objects and their evaluated geometry, not
standalone curves, volumes or unrealized instances. Simulation-dependent poses
require an appropriate baked cache; sampling does not bake simulations.
`tests/python/blaya_onion_skin.py` exercises GPU drawing, panel rendering,
evaluated modifiers/rig deformation, frame restoration, scrubbing, cache
cleanup and the geometry limit in a disposable GUI scene.

## Circular modeling

In mesh Edit Mode, select a closed edge loop (such as a hole boundary) and use
**Model → Modeling Tools → Shape / Spacing → Circularize**. The tool is also available
through search, the custom shelf tool list and the Maya learning map.

The dialog offers Best Fit or world-axis planes, fitted/selection/cursor
centers, exact world-space Radius (zero fits automatically), Even Spacing,
Flatten and Influence. Separate disconnected loops get independent circles;
a cursor center is shared when explicitly chosen. Nonuniform object scale is
accounted for. Vertex positions change, while edges, faces and unselected
vertices remain intact. Flatten off preserves depth along the chosen normal.

Select only loop vertices, not an entire filled region. Open chains, branches,
collinear selections and unsuitable center/plane combinations are rejected
before any edited mesh is changed. Unconnected vertices can also be rounded.
The operation supports Undo and Adjust Last Operation.

`tests/python/blaya_circular.py` checks fitted centers, spacing, radius,
influence, depth, quad-hole preservation, world-space scale, separate loops
and rejection without partial edits.

New scenes and factory startup use Imperial units with Separate Units enabled
(feet and inches). Unit Scale remains 1.0; this changes measurement display,
not geometry size. Saved scenes retain their own unit settings.

## Autosave

Kitchen 3D initializes automatic recovery saves to every **5 minutes**. Change the
interval or toggle it in **Kitchen 3D Tools → Setup → Auto Save**, then use **Save
Preferences** to retain the choice. Later initialization preserves your chosen
interval and toggle. This uses Blender's temporary recovery saves; it does not
replace manual saving of the working file. Recover through **File → Recover →
Auto Save**. A running modal operation can defer a scheduled save until it ends.

## Shape tools and live previews

**Model → Modeling Tools → Shape / Spacing** contains Circularize, Relax,
Space and Straighten. Their dialogs preview immediately and recompute from
the original coordinates as controls change. **Apply** commits the result;
**Cancel** or Escape restores the starting shape. Invalid settings restore the
starting shape and show a message in the dialog. Undo remains available.

Relax smooths selected open chains or closed loops with adjustable strength
and iterations; closed loops can shrink. Space redistributes vertices by arc
length along the original polyline; corners can soften. Straighten aligns an
open chain between its endpoints while retaining proportional path distances.
All three preserve open-chain endpoints. They preserve topology and work in
world space, including nonuniform object scale. Select chains/loops without
branches or interior vertices. Each disconnected chain is handled separately.

`tests/python/blaya_loop_tools.py` checks the geometry and preview transaction,
including repeated recomputation, Apply, Cancel, and invalid preview restoration.

## Brand lockup and sculpt learning map

The transparent brand lockup in `release/branding/blaya-lockup.svg` pairs the
Kitchen 3D stove mark and name with the text **Blender Distro**.
The app menu and About use the Kitchen 3D mark; the native window title identifies
Kitchen 3D | Blender Distro and the upstream version. Native title bars use plain
text, while the vector lockup preserves the requested relative type sizes.
Blender's upstream credits and support links remain available.

**Kitchen 3D Tools → Sculpt → ZBrush → Blender Learning Map** is collapsed by default.
Search either application's terminology, including Standard, Move, ClayBuildup,
DamStandard, Smooth, Mask, PolyGroups, DynaMesh, Sculptris Pro, subdivision,
ZRemesher, SubTools, symmetry, LazyMouse and navigation. Hover a result for its
Blender workflow, location and differences. Search is also available through
**Search ZBrush → Blender Learning Map** in operator search. The map is guidance;
it does not install ZBrush key bindings or execute remeshing operations.

## Kitchen 3D naming compatibility

The public application name is Kitchen 3D. Internal `blaya` modules, operator
IDs, saved RNA identifiers, asset filenames, bundle identifiers, and the existing
`Blaya` preferences directory stay stable so existing workspaces and settings
remain compatible. Opening a legacy BLAYA workspace through the workspace
command reuses it and updates its displayed name. The stove mark is used in the app icon, splash screen, menu, and About dialog.
