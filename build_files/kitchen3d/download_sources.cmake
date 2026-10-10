# SPDX-License-Identifier: GPL-2.0-or-later
# Download the dependency sources without configuring a dependency build.
cmake_minimum_required(VERSION 3.22)
if(NOT PACKAGE_DIR)
  message(FATAL_ERROR "Pass -DPACKAGE_DIR=/absolute/output/path")
endif()
file(MAKE_DIRECTORY "${PACKAGE_DIR}")
include("${CMAKE_CURRENT_LIST_DIR}/../build_environment/cmake/versions.cmake")

# The release mirror can lag a dependency version bump. Try the main mirror
# and the dependency author's URL too, always enforcing the pinned hash.
function(fetch_source dep)
  set(destination "${PACKAGE_DIR}/${${dep}_FILE}")
  if(EXISTS "${destination}")
    file(${${dep}_HASH_TYPE} "${destination}" actual_hash)
    if(actual_hash STREQUAL "${${dep}_HASH}")
      return()
    endif()
  endif()
  foreach(url IN ITEMS
      "https://projects.blender.org/blender/lib-source/media/branch/blender-v5.3-release/${${dep}_FILE}"
      "https://projects.blender.org/blender/lib-source/media/branch/main/${${dep}_FILE}"
      "${${dep}_URI}")
    message(STATUS "Downloading ${dep}: ${url}")
    file(DOWNLOAD "${url}" "${destination}.partial"
      TIMEOUT 1800 TLS_VERIFY ON STATUS status)
    list(GET status 0 code)
    if(code EQUAL 0)
      file(${${dep}_HASH_TYPE} "${destination}.partial" actual_hash)
      if(actual_hash STREQUAL "${${dep}_HASH}")
        file(RENAME "${destination}.partial" "${destination}")
        return()
      endif()
      message(STATUS "Rejected ${dep}: hash mismatch")
    endif()
    file(REMOVE "${destination}.partial")
  endforeach()
  message(FATAL_ERROR "No verified source download available for ${dep}")
endfunction()

# Follow upstream's dependency list without maintaining a second copy.
file(READ "${CMAKE_CURRENT_LIST_DIR}/../build_environment/cmake/download.cmake" upstream)
string(REGEX MATCHALL "download_source\\([A-Z0-9_]+\\)" downloads "${upstream}")
foreach(download IN LISTS downloads)
  string(REGEX REPLACE "download_source\\(([A-Z0-9_]+)\\)" "\\1" dep "${download}")
  fetch_source(${dep})
endforeach()
