#!/bin/sh
# SPDX-FileCopyrightText: 2026 Kitchen 3D contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# Regenerate both macOS icon formats from the editable Icon Composer document.
set -eu
icon_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
icon_build=$(mktemp -d)
trap 'rm -rf "$icon_build"' EXIT HUP INT TERM
xcrun actool "$icon_dir/blaya.icon" --compile "$icon_build" \
  --platform macosx --minimum-deployment-target 11.2 --app-icon blaya \
  --output-partial-info-plist "$icon_build/partial.plist" \
  --output-format human-readable-text
cp "$icon_build/Assets.car" "$icon_build/blaya.icns" \
  "$icon_dir/Blender.app/Contents/Resources/"
