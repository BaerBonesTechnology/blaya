# Kitchen 3D CI and downloads

The **Kitchen 3D builds** GitHub Actions workflow builds Windows x64, Linux x64,
and macOS arm64 independently. Pull requests run the same builds and tests with
read-only repository permissions. Pushes to `codex/kitchen3d-5.3` and tags matching
`kitchen3d-v*` publish a preview only after every build and the source archive job
succeed. Manual runs publish only when **publish** is checked.

Each release has its own run-specific tag and is published from a draft after
all assets upload. A failed run leaves previous releases available. The README
download button opens Releases, including beta previews. CI artifacts expire
after 14 days; published release downloads do not have that expiration.

## Packages and coverage

| Download | Target | Launch after extracting |
| --- | --- | --- |
| `Kitchen3D-windows-x64.zip` | Windows x64 | `blender.exe` |
| `Kitchen3D-linux-x64.tar.xz` | Ubuntu 24.04 x64 or compatible | `Kitchen3D-linux-x64/blender` |
| `Kitchen3D-macos-arm64.zip` | Apple Silicon macOS | `Kitchen 3D.app` |

Packages retain upstream license notices and include `COPYING`, `doc/license`,
and `BUILD.json` identifying the exact source revision. Each package has a
SHA-256 checksum. The Windows executable retains its internal upstream filename.
These are unsigned previews, not installers; macOS notarization and Windows
code signing require developer certificates and are not configured.

The four background suites cover Kitchen 3D geometry, circularize, loop tools,
and animation/pose behavior. A separate smoke test checks the installed Python
and NumPy runtime, renders with Cycles CPU, and saves/reopens a `.blend` file.
Packaging runs only after these tests pass. Diagnostics upload even on failure.
GUI/isolation/screenshot tests and the full upstream C++ suite are not run on
hosted runners. The existing optional GUI suites remain available locally.

`ci.cmake` starts from Blender's release preset and disables CUDA, OptiX, HIP,
oneAPI, and DLSS because their compiler/SDK toolchains are not installed on
these runners. Cycles CPU, Eevee, and macOS Metal remain enabled. The initial
workflow performs clean builds with three parallel compiler jobs; expect long
builds rather than quick application-only CI. No signing secrets are needed.

## Reproduce a build

Use the source commit recorded in the release and install the platform's
[Blender build prerequisites](https://developer.blender.org/docs/handbook/building_blender/).
Git LFS assets come from Blender's upstream LFS endpoint; the customized artwork
is stored directly in this fork. Platform libraries use the exact Git submodule
commit recorded by the fork, never a floating release-branch tip.

```sh
git -c lfs.url=https://projects.blender.org/blender/blender.git/info/lfs lfs pull
# Choose linux_x64, windows_x64, or macos_arm64.
git submodule update --init --checkout -- lib/linux_x64
git -C lib/linux_x64 lfs pull
cmake -S . -B build -G Ninja -C build_files/kitchen3d/ci.cmake \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PWD/install"
cmake --build build --target install --parallel 3
ctest --test-dir build -C Release -L kitchen3d --output-on-failure --no-tests=error
```

On Windows run configuration/build commands in a VS 2022 x64 developer shell;
the source requires MSVC 19.44.35216 or newer. See the workflow for exact runner
labels, Python test configuration, and smoke-test invocation.

## Release source archives

`Kitchen3D-source.tar.xz` contains the tracked fork source, materialized LFS
assets, notices, patches, dependency build recipes, and this workflow. Binary
library submodules are omitted; their pinned commits remain in the release's
Git tree. The separate dependency archive contains the source packages selected
by `build_files/build_environment/cmake/versions.cmake`, verified against its
hashes. Source download failure blocks publication.

Download **every** dependency part, then concatenate them in numerical order:

```sh
sha256sum -c SOURCE-SHA256SUMS.txt
cat Kitchen3D-dependency-sources.tar.part* > Kitchen3D-dependency-sources.tar
tar -xf Kitchen3D-dependency-sources.tar
tar -xf Kitchen3D-source.tar.xz
```

On macOS use `shasum -a 256 -c SOURCE-SHA256SUMS.txt`. On Windows use `Get-FileHash`
to verify the parts and a binary concatenation tool (for example `cat` in Git
Bash) to join them. Parts are below GitHub's per-asset size limit.

To rebuild dependencies from source, follow the included
`build_files/build_environment` platform scripts, setting their CMake
`PACKAGE_DIR` to the extracted `dependency-sources` directory. The included
patches and recipes describe how those sources are built. Alternatively, clone
the exact fork revision and use its pinned precompiled library submodules as
CI does. An extracted source archive alone is not a Git checkout and cannot
run `git submodule update`.
