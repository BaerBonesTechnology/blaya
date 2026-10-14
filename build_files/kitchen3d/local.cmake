# SPDX-License-Identifier: GPL-2.0-or-later
include("${CMAKE_CURRENT_LIST_DIR}/ci.cmake")
# Local builds do not require the GitHub-hosted compiler cache service.
set(WITH_WINDOWS_SCCACHE OFF CACHE BOOL "Local build" FORCE)
