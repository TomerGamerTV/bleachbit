#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_root="${repo_root}/build/macos"
dist_root="${repo_root}/dist/macos"
pyinstaller_dist_root="${dist_root}/pyinstaller"
venv_dir="${build_root}/venv"
iconset_dir="${build_root}/BleachBit.iconset"
icon_path="${build_root}/BleachBit.icns"
pyinstaller_version="6.19.0"

log() {
    printf '[build-macos-app] %s\n' "$*"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Missing required command: %s\n' "$1" >&2
        exit 1
    fi
}

prepare_translations() {
    if command -v msgfmt >/dev/null 2>&1; then
        log "Building local translations"
        make -C "${repo_root}/po" local PYTHON=python3
    else
        log "Skipping translations because gettext tools are unavailable"
    fi
}

prepare_icon() {
    if ! command -v iconutil >/dev/null 2>&1; then
        log "iconutil not found; using the default app icon"
        return 1
    fi

    require_command sips

    rm -rf "${iconset_dir}"
    mkdir -p "${iconset_dir}"

    while read -r size name; do
        sips -z "${size}" "${size}" "${repo_root}/bleachbit.png" \
            --out "${iconset_dir}/${name}" >/dev/null
    done <<'EOF'
16 icon_16x16.png
32 icon_16x16@2x.png
32 icon_32x32.png
64 icon_32x32@2x.png
128 icon_128x128.png
256 icon_128x128@2x.png
256 icon_256x256.png
512 icon_256x256@2x.png
512 icon_512x512.png
1024 icon_512x512@2x.png
EOF

    iconutil -c icns -o "${icon_path}" "${iconset_dir}"
}

main() {
    if [[ "$(uname -s)" != "Darwin" ]]; then
        printf 'This build script only supports macOS.\n' >&2
        exit 1
    fi

    require_command python3
    require_command make

    mkdir -p "${build_root}" "${dist_root}"

    if [[ ! -d "${venv_dir}" ]]; then
        log "Creating build virtualenv with system site-packages"
        python3 -m venv --system-site-packages "${venv_dir}"
    fi

    # shellcheck disable=SC1091
    source "${venv_dir}/bin/activate"

    log "Installing build dependencies"
    python -m pip install --upgrade pip setuptools wheel \
        "pyinstaller==${pyinstaller_version}"
    python -m pip install -r "${repo_root}/requirements.txt"

    log "Checking Python GTK dependencies"
    python - <<'PY'
import cairo
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk
print('GTK build dependencies available')
PY

    prepare_translations

    app_version="$(python - <<'PY'
import bleachbit
print(bleachbit.APP_VERSION)
PY
)"

    icon_flag=()
    if prepare_icon; then
        icon_flag=(--icon "${icon_path}")
    fi

    log "Building PyInstaller payload"
    rm -rf "${pyinstaller_dist_root}" "${dist_root}/BleachBit.app" \
        "${build_root}/pyinstaller" "${build_root}/spec"

    pyinstaller \
        --noconfirm \
        --clean \
        --name BleachBit \
        --distpath "${pyinstaller_dist_root}" \
        --workpath "${build_root}/pyinstaller" \
        --specpath "${build_root}/spec" \
        --paths "${repo_root}" \
        --add-data "${repo_root}/COPYING:." \
        --add-data "${repo_root}/bleachbit.png:." \
        --add-data "${repo_root}/cleaners:cleaners" \
        --add-data "${repo_root}/share:share" \
        --add-data "${repo_root}/themes:themes" \
        --collect-all gi \
        --collect-all cairo \
        --hidden-import gi.repository.Gdk \
        --hidden-import gi.repository.Gio \
        --hidden-import gi.repository.GLib \
        --hidden-import gi.repository.GObject \
        --hidden-import gi.repository.Gtk \
        "${icon_flag[@]}" \
        "${repo_root}/bleachbit.py"

    log "Wrapping payload into BleachBit.app"
    app_dir="${dist_root}/BleachBit.app"
    mkdir -p "${app_dir}/Contents/MacOS" "${app_dir}/Contents/Resources"

    rsync -a "${pyinstaller_dist_root}/BleachBit/" "${app_dir}/Contents/MacOS/"
    ln -sfn "MacOS/_internal" "${app_dir}/Contents/Frameworks"

    if [[ -d "${repo_root}/locale" ]]; then
        rsync -a "${repo_root}/locale/" \
            "${app_dir}/Contents/MacOS/_internal/locale/"
    fi

    if [[ -f "${icon_path}" ]]; then
        cp "${icon_path}" "${app_dir}/Contents/Resources/BleachBit.icns"
        icon_file_key='<key>CFBundleIconFile</key><string>BleachBit.icns</string>'
    else
        icon_file_key=''
    fi

    cat > "${app_dir}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>BleachBit</string>
    <key>CFBundleExecutable</key>
    <string>BleachBit</string>
    <key>CFBundleIdentifier</key>
    <string>org.bleachbit.BleachBit</string>
    ${icon_file_key}
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>BleachBit</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>${app_version}</string>
    <key>CFBundleVersion</key>
    <string>${app_version}</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

    printf 'APPL????' > "${app_dir}/Contents/PkgInfo"

    log "Built app bundle: ${dist_root}/BleachBit.app"
    log "Launch it from Finder or run: open \"${dist_root}/BleachBit.app\""
}

main "$@"
