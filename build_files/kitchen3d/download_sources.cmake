# SPDX-License-Identifier: GPL-2.0-or-later
# Download the dependency sources without configuring a dependency build.
cmake_minimum_required(VERSION 3.22)
if(NOT PACKAGE_DIR)
  message(FATAL_ERROR "Pass -DPACKAGE_DIR=/absolute/output/path")
endif()
file(MAKE_DIRECTORY "${PACKAGE_DIR}")
include("${CMAKE_CURRENT_LIST_DIR}/../build_environment/cmake/versions.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/../build_environment/cmake/download.cmake")
