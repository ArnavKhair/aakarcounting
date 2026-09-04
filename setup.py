#!/usr/bin/env python3
"""
Build script for Vehicle Counting AI .app launcher.

Creates a lightweight macOS .app bundle that launches the Python app
from the project's virtual environment via Terminal.app.

Usage:
    source venv/bin/activate
    python setup.py

The .app will be created at: VehicleCountingAI.app
"""
import os
import shutil
import stat

APP_NAME = "VehicleCountingAI"
APP_DIR = f"{APP_NAME}.app"
CONTENTS = os.path.join(APP_DIR, "Contents")
MACOS_DIR = os.path.join(CONTENTS, "MacOS")
RESOURCES_DIR = os.path.join(CONTENTS, "Resources")

INFO_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>VehicleCountingAI</string>
    <key>CFBundleDisplayName</key>
    <string>Vehicle Counting AI</string>
    <key>CFBundleIdentifier</key>
    <string>com.aakar.vehiclecounting</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>VehicleCountingAI</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Vehicle Counting AI - Multi-Model Comparison for Indian Roads</string>
</dict>
</plist>
"""

LAUNCHER = r"""#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
MAIN_PY="$SCRIPT_DIR/main.py"
COMMAND_FILE="$SCRIPT_DIR/.vehicle_ai_launch.command"

if [ ! -d "$VENV_DIR" ]; then
    osascript -e 'display dialog "Cannot find Python virtual environment at:\n'"$VENV_DIR"'" buttons {"OK"} default button 1 with title "Vehicle Counting AI"'
    exit 1
fi

if [ ! -f "$MAIN_PY" ]; then
    osascript -e 'display dialog "Cannot find main.py at:\n'"$MAIN_PY"'" buttons {"OK"} default button 1 with title "Vehicle Counting AI"'
    exit 1
fi

PYTHON="$VENV_DIR/bin/python"

cat > "$COMMAND_FILE" << SCRIPT
#!/bin/bash
cd "$SCRIPT_DIR"
"$PYTHON" main.py
rm -f "$COMMAND_FILE"
SCRIPT

chmod +x "$COMMAND_FILE"
open "$COMMAND_FILE"
"""


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(project_dir, APP_DIR)

    if os.path.exists(app_dir):
        print(f"Removing existing {APP_DIR}...")
        shutil.rmtree(app_dir)

    os.makedirs(MACOS_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)

    plist_path = os.path.join(CONTENTS, "Info.plist")
    with open(plist_path, "w") as f:
        f.write(INFO_PLIST)

    launcher_path = os.path.join(MACOS_DIR, APP_NAME)
    with open(launcher_path, "w") as f:
        f.write(LAUNCHER)
    os.chmod(launcher_path, os.stat(launcher_path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Created {APP_DIR}")
    print(f"  Double-click to launch, or run: open {APP_DIR}")
    print(f"  You can move it to /Applications if desired.")


if __name__ == "__main__":
    main()
