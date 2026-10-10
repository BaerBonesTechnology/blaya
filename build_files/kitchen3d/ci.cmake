# SPDX-License-Identifier: GPL-2.0-or-later
include("${CMAKE_CURRENT_LIST_DIR}/../cmake/config/blender_release.cmake")

# Hosted runners do not include the proprietary GPU compiler SDKs.
foreach(feature IN ITEMS
    WITH_CYCLES_DEVICE_CUDA WITH_CYCLES_CUDA_BINARIES
    WITH_CYCLES_DEVICE_OPTIX WITH_CYCLES_DEVICE_HIP WITH_CYCLES_DEVICE_HIPRT
    WITH_CYCLES_HIP_BINARIES WITH_CYCLES_DEVICE_ONEAPI WITH_CYCLES_ONEAPI_BINARIES
    WITH_DLSS WITH_GTESTS WITH_KITCHEN3D_UI_TESTS)
  set(${feature} OFF CACHE BOOL "Kitchen 3D hosted CI" FORCE)
endforeach()
set(WITH_INSTALL_PORTABLE ON CACHE BOOL "Portable download" FORCE)
set(WITH_STRICT_BUILD_OPTIONS ON CACHE BOOL "Fail on missing dependencies" FORCE)
