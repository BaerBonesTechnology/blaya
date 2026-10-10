# Kitchen 3D

A personal Blender build, shaped around the way I work.

[![Download Kitchen 3D](https://img.shields.io/badge/Download-Kitchen_3D-208C87?style=for-the-badge&logo=github)](https://github.com/BaerBonesTechnology/blaya/releases)
[![Build and tests](https://github.com/BaerBonesTechnology/blaya/actions/workflows/kitchen3d.yml/badge.svg)](https://github.com/BaerBonesTechnology/blaya/actions/workflows/kitchen3d.yml)

Choose **Windows x64**, **Linux x64**, or **macOS Apple Silicon** from the
release assets. Downloads appear after the first successful cross-platform
pipeline. Extract the package before launching; these preview builds are
unsigned and macOS builds are not notarized. Linux packages target Ubuntu 24.04
or compatible distributions. Intel Macs and Windows/Linux ARM are not included.

Kitchen 3D brings familiar Maya-style workflows into Blender: a focused modeling
layout, a dedicated tools panel, and shortcuts that make everyday work feel
natural. This is my daily workspace. Its direction comes from using it on real
projects and improving the things that get in the way.

## The workspace

- **Modeling first.** Start with a full modeling viewport and the Kitchen 3D
  tools panel. Open the UV editor when needed. Saved files keep their layouts.
- **Selection isolation.** Ctrl-I isolates selected objects, recalled component
  sets, or vertices, edges and faces. Press it again to restore visibility,
  including geometry that was already hidden.
- **Interactive shape tools.** Circularize, Relax, Space and Straighten offer
  live previews, viewport dragging, multi-object editing and optional surface
  projection. Cancel restores the original geometry; shape-key edits require
  explicit opt-in.
- **UV tools.** Texel-density presets and UDIM distribution preserve control
  over scale, padding and island placement.
- **Animation tools.** A dedicated animation workspace, selected-channel
  keying, timing controls and cached viewport onion skins.
- **Familiar controls.** Industry Compatible defaults, customizable shelves,
  and Maya/Blender and ZBrush/Blender terminology maps.

## Current build

The current base is the **Blender 5.3 release branch**, which identifies this
build as **5.3.0 Beta**. The native application is built and tested on
**macOS / Apple Silicon** as `Kitchen 3D.app`. The CI pipeline builds and tests
Windows, Linux, and macOS before publishing a preview. See its status above for
the latest result; platform support is not confirmed until that build passes.

Hosted builds include Cycles CPU rendering and macOS Metal support. Windows and
Linux CUDA, OptiX, HIP and oneAPI backends are disabled in this initial pipeline.

The workflow tools are integrated into this fork. Internal `blaya` identifiers
and existing preferences paths remain compatible with earlier builds.

See the [integration and workflow notes](BLAYA.md) for tool details,
preferences, branding assets and compatibility information.

## Building and testing

Start with the [Blender build instructions](https://developer.blender.org/docs/handbook/building_blender/)
for the upstream dependencies and platform setup, then build this checkout's
`install` target.

The [CI and release guide](build_files/kitchen3d/README.md) explains automated
tests, portable packages, manual runs, and rebuilding the downloadable source.

Run the Kitchen 3D regression suites against the installed build:

```sh
ctest --test-dir /path/to/build -L kitchen3d --output-on-failure
```

Configure with `-DWITH_KITCHEN3D_UI_TESTS=ON` to include GUI checks; these require
an active display. The macOS build passed all nine suites, covering geometry,
selection isolation, Undo/Redo, workspace setup, UV routing, animation, caching
and UI snapshots. Save/reopen and a Cycles CPU render were also verified.

## Built on Blender

Blender provides the modeling, rigging, animation, simulation, rendering,
compositing and editing foundation. Kitchen 3D is an independent customization;
it is not affiliated with or endorsed by the Blender Foundation. Blender's
credits and license notices remain intact.

- [Blender](https://www.blender.org/)
- [Reference manual](https://docs.blender.org/manual/en/latest/)
- [Developer documentation](https://developer.blender.org/docs/)
- [Upstream code and issue tracker](https://projects.blender.org)
- [Community](https://www.blender.org/community/)
- [Support Blender development](https://fund.blender.org/)

## License

Blender as a whole is licensed under the GNU General Public License, Version 3.
Individual files may have a different but compatible license.

See [Blender's license information](https://www.blender.org/about/license/) for details.
