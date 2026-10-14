# Kitchen 3D builds

## 5.4 alpha local builds

`kitchen3d-5.4-alpha` follows Blender `main`. The release-packaging and installer
workflows are removed on this branch. There are no automatic alpha CI builds,
release archives, or uploads. The CI documentation below describes the separate
5.3 branches.

Install Blender's platform build prerequisites, CMake, Ninja, Python 3, Git and
Git LFS. Run from the checkout:

```sh
python3 build_files/kitchen3d/build_local.py --prepare
```

The script fetches pinned platform libraries and upstream LFS assets when
`--prepare` is supplied, configures a Release build, installs the app locally,
and runs the Kitchen 3D background regression suites. It does not create a
release or upload anything. The default build directory is the sibling
`build_kitchen3d_5.4_alpha`; the app goes in its `install` subdirectory, keeping
the 5.3 build separate. Subsequent builds can omit `--prepare` unless dependencies
change. Use `--jobs`, `--build-dir`, `--install-dir`, and `--cmake` to customize
local paths, or `--dry-run` to inspect commands first.

Windows: use a VS 2022 x64 developer shell with CUDA 12.8 available and OptiX
headers installed. Run `python` instead of `python3` if needed and pass
`--optix-root C:/path/to/optix`. NVIDIA kernels are built locally; sccache is
optional and not required. macOS Apple Silicon uses Metal; Linux x64 uses the
CPU configuration. Other architectures are not configured by this script.

## 5.3 CI and downloads reference


The **Kitchen 3D builds** GitHub Actions workflow builds Windows x64, Linux x64,
and macOS arm64 independently. Pushes to `kitchen3d-5.3` and tags matching
`kitchen3d-v*` publish a preview only after every build and the source archive job
succeed. Manual runs publish only when **publish** is checked.

Each release has its own run-specific tag and is published from a draft after
all assets upload. A failed run leaves previous releases available. The README
download button opens Releases, including beta previews. CI artifacts expire
after 14 days; published release downloads do not have that expiration.

## Development tests

Work on `development` and promote changes to `kitchen3d-5.3` when
ready for a release. **Kitchen 3D development tests** runs on development pushes
and pull requests targeting either branch. It uses read-only permissions and a
checksum-pinned Windows release executable to run the current Python tools and
six background suites, including a real glTF export regression. The glTF test
loads the exporter from the checkout rather than from the downloaded runtime.

This workflow creates no installers, release archives, source bundles, uploaded
artifacts, or releases. Results are in the Actions logs. New pushes cancel only
obsolete development test runs; the release workflow uses separate concurrency.

This is a Python regression gate, not native build or GUI validation. C/C++
changes still require a native build before promotion. Release builds retain
the full Windows/Linux/macOS build, render, packaging and installer checks.
The new development workflow and release-trigger changes take effect from this
branch; the production branch is unchanged until promotion.

## Packages and coverage

| Download | Target | Launch after extracting |
| --- | --- | --- |
| `Kitchen3D-windows-x64-setup.exe` | Windows x64 | Run the installation wizard |
| `Kitchen3D-windows-x64.zip` | Windows x64 | `kitchen3d.exe` |
| `Kitchen3D-linux-x64.tar.xz` | Ubuntu 24.04 x64 or compatible | `Kitchen3D-linux-x64/kitchen3d` |
| `Kitchen3D-macos-arm64.zip` | Apple Silicon macOS | `Kitchen 3D.app` |

Packages retain upstream license notices and include `COPYING`, `doc/license`,
and `BUILD.json` identifying the exact source revision. Each package has a
SHA-256 checksum. The executables and desktop launchers use the Kitchen 3D name.
Windows also includes `kitchen3d-launcher.exe` for starting without a console;
Linux includes `kitchen3d-launcher` for bundled-library setup. CI smoke-tests
these launchers as well as testing the main executables. Package from a clean
install directory: older builds may leave a stale `blender.exe` or `blender`
beside the renamed executable, which the packager will reject.
These are unsigned previews; macOS notarization and Windows
code signing require developer certificates and are not configured.

The Windows installer uses Inno Setup 6 and installs for the current user under
`%LOCALAPPDATA%\Programs\Kitchen3D` by default, without requiring administrator
rights. The location is configurable. It creates a Start menu shortcut, offers
an optional desktop shortcut, and registers an uninstaller in Windows Settings.
The shortcuts use the stove icon and launch `kitchen3d-launcher.exe`.
Subsequent Setup runs reuse the existing location. Uninstall removes installed
files and shortcuts; it does not delete preferences or user-created project files.
Setup offers **Standalone** (the default) or **Use Kitchen 3D for .blend files**.
The second option registers Kitchen 3D as a file handler and opens Windows Default
Apps on the finish page; select Kitchen 3D for `.blend` there to complete the change.
Both options keep Blender installed. Setup never overwrites Blender's registrations
or Windows' protected user choice. Uninstall removes Kitchen 3D's registrations;
Windows may ask you to choose another default afterward.

CI compiles the installer after packaging, then installs it into a temporary
path containing spaces, checks the shortcuts and uninstall entry, installs it
again to test upgrading, runs the installed launcher and render smoke tests,
and uninstalls. It verifies that a user-created file survives both operations.
Publication is blocked if any installer check fails. The manually dispatched
**Validate Windows installer** workflow provides a faster test with a pinned,
checksum-verified executable fixture with the current Kitchen Python tools; its artifacts are validation builds, not a
replacement for a release built from the current source.

To compile an installer on Windows after `package.py` has produced `BUILD.json`
and copied the notices, install Inno Setup 6 and run:

```sh
python build_files/kitchen3d/build_installer.py --install install --output dist
```

The six background suites cover Kitchen 3D geometry, circularize, loop tools,
animation/pose behavior, glTF instancing and render benchmark selection. A separate smoke test checks the installed Python
and NumPy runtime, renders with Cycles CPU, and saves/reopens a `.blend` file.
Packaging runs only after these tests pass. Diagnostics upload even on failure.
GUI/isolation/screenshot tests and the full upstream C++ suite are not run on
hosted runners. The existing optional GUI suites remain available locally.

Windows builds on this development branch enable NVIDIA CUDA and OptiX using
CUDA 12.8.0 and pinned OptiX 9.0 headers. CUDA kernels and OptiX PTX are packaged;
users need a supported NVIDIA driver, not the compiler toolkit. AMD HIP, Intel
oneAPI and DLSS remain disabled. Linux Cycles remains CPU-only; macOS retains Metal.

Compiler outputs are cached with pinned sccache 0.16 using GitHub's cache backend,
separated by platform. Compiler, flags and source/header hashes determine reuse.
The first build populates the cache; linking, tests, downloads and packaging still
run. GitHub branch cache visibility and eviction affect reuse. Cache statistics
appear in build logs. Dependency archives and library downloads are not cached
by this change.

**Windows GPU build tests** compiles Windows on development when the GPU build
configuration changes, and can be manually dispatched. It checks compiled backend
flags and installed CUDA/OptiX kernels, runs regressions and smoke tests, and
creates no release packages or uploaded artifacts. Hosted runners cannot verify
actual GPU rendering; a supported NVIDIA machine must run the benchmark.

## Windows render benchmark

New sessions prefer a detected NVIDIA GPU (OptiX before CUDA); turn off **Prefer
GPU on Windows startup** in Setup to opt out. Opening existing project files does
not change their saved render settings. Existing configured compute devices are
respected.

In **Setup → Cycles Performance**, choose **Benchmark & Optimize Cycles**.
A separate process with isolated preferences renders a fixed 256px scene at
32 samples, warms up each device and takes two timed measurements. It compares
individual NVIDIA devices via OptiX/CUDA and CPU thread counts. The fastest
successful GPU wins; CPU is selected only if no GPU succeeds. Escape cancels;
the overall timeout is ten minutes. Process failure or cancellation does not
apply a result. The benchmark temporarily uses system compute resources.

The result configures the scene that started the benchmark and Cycles device
preferences. Samples, resolution, engine, bounces and denoising remain unchanged.
Save your project and preferences to retain the result. This small scene estimates
device throughput; it does not prove that a large production scene fits GPU memory
or that the same device is fastest for every workload.

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
assets, notices, patches, dependency build recipes, and this workflow. The large
upstream test fixtures under `tests/files` and binary library submodules are omitted; their pinned commits remain in the release's
Git tree and `SOURCE-REVISION.json` inside the archive. The separate dependency
archive contains the source packages selected
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
