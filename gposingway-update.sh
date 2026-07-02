#!/usr/bin/env bash
# GPosingway Linux launcher for the python updater script

# Exit on absolute failures of environment checks
set -euo pipefail

# Find script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "\033[91mError: python3 is not installed on this system.\033[0m"
    echo "GPosingway installer requires Python 3. Please install it using your package manager."
    echo "  Arch Linux: sudo pacman -S python"
    echo "  Ubuntu/Debian: sudo apt install python3"
    echo "  Fedora: sudo dnf install python3"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Auto-download the companion python script if missing
PY_SCRIPT="${SCRIPT_DIR}/gposingway-update.py"
if [ ! -f "$PY_SCRIPT" ]; then
    echo -e "\033[94mℹ Downloading installer companion script...\033[0m"
    TEMP_PY="${SCRIPT_DIR}/gposingway-update.py.tmp"
    DOWNLOAD_OK=0
    
    # Use -f / --fail to return error status on 404
    if command -v curl &> /dev/null; then
        curl -s -f -o "$TEMP_PY" "https://raw.githubusercontent.com/gposingway/gposingway/main/gposingway-update.py" && DOWNLOAD_OK=1
    elif command -v wget &> /dev/null; then
        wget -q -O "$TEMP_PY" "https://raw.githubusercontent.com/gposingway/gposingway/main/gposingway-update.py" && DOWNLOAD_OK=1
    fi
    
    # Check if download succeeded and file is valid python (not 404 html/text)
    if [ "$DOWNLOAD_OK" -eq 1 ] && [ -s "$TEMP_PY" ] && ! grep -q "Not Found" "$TEMP_PY" && ! grep -q "404" "$TEMP_PY"; then
        mv "$TEMP_PY" "$PY_SCRIPT"
        chmod +x "$PY_SCRIPT"
    else
        rm -f "$TEMP_PY"
        echo -e "\033[91mError: Could not download the companion Python script from GitHub.\033[0m"
        echo "Since the project is not yet fully updated on GitHub, please make sure to"
        echo "manually copy 'gposingway-update.py' next to this '.sh' script."
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# Run the python installer script
python3 "$PY_SCRIPT" "$@"
