#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
project_root=${script_dir:h}
source_root="${project_root}/helpers/macos"
output_root="${project_root}/dist/macos"
temporary_root=$(mktemp -d)
trap 'rm -rf "${temporary_root}"' EXIT

status_app="${temporary_root}/Kick75 Codex Status.app"
sidebar_app="${temporary_root}/Kick75 Codex Sidebar.app"
status_archive="${output_root}/Kick75-Codex-Status-macOS.zip"
sidebar_archive="${output_root}/Kick75-Codex-Sidebar-macOS.zip"

mkdir -p "${output_root}"
rm -f "${status_archive}" "${sidebar_archive}"
mkdir -p "${status_app}/Contents/MacOS" "${status_app}/Contents/Resources"
mkdir -p "${sidebar_app}/Contents/MacOS"

xcrun clang -fobjc-arc -framework Foundation -framework IOKit \
  "${source_root}/Kick75CodexStatus.m" \
  -o "${temporary_root}/Kick75CodexStatus"

install -m 755 "${temporary_root}/Kick75CodexStatus" "${status_app}/Contents/MacOS/Kick75CodexStatus"
install -m 644 "${source_root}/Kick75CodexStatus-Info.plist" "${status_app}/Contents/Info.plist"
install -m 644 "${source_root}/codex_status.py" "${status_app}/Contents/Resources/codex_status.py"

xcrun swiftc -framework AppKit -framework ApplicationServices \
  "${source_root}/Kick75CodexSidebar.swift" \
  -o "${temporary_root}/Kick75CodexSidebar"

install -m 755 "${temporary_root}/Kick75CodexSidebar" "${sidebar_app}/Contents/MacOS/Kick75CodexSidebar"
install -m 644 "${source_root}/Kick75CodexSidebar-Info.plist" "${sidebar_app}/Contents/Info.plist"

xattr -cr "${status_app}"
codesign --force --deep --sign - "${status_app}"
codesign --verify --deep --strict "${status_app}"

xattr -cr "${sidebar_app}"
codesign --force --deep --sign - "${sidebar_app}"
codesign --verify --deep --strict "${sidebar_app}"

ditto -c -k --norsrc --keepParent "${status_app}" "${status_archive}"
ditto -c -k --norsrc --keepParent "${sidebar_app}" "${sidebar_archive}"

printf 'Built %s\n' "${status_archive}"
printf 'Built %s\n' "${sidebar_archive}"
