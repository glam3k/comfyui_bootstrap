#!/bin/bash

# ComfyUI Bootstrap Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/glam3k/comfyui_bootstrap/main/install.sh | bash -s -- [port]

PORT=${1:-8188}
REPO_URL="https://github.com/glam3k/comfyui_bootstrap.git"
DIR_NAME="comfyui_bootstrap"

# Check for essential dependencies
check_deps() {
    local deps=("python3" "git" "curl" "wget" "ufw")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            echo "Missing dependency: $dep. Installing..."
            sudo apt-get update && sudo apt-get install -y "$dep" || {
                echo "Failed to install $dep. Please install it manually."
                exit 1
            }
        fi
    done
}

echo "Starting ComfyUI Bootstrap installation..."
check_deps

# Clone the repository
if [ ! -d "$DIR_NAME" ]; then
    echo "Cloning bootstrap repository..."
    git clone "$REPO_URL" "$DIR_NAME"
fi

# Execute the bootstrap script
echo "Running bootstrap script on port $PORT..."
cd "$DIR_NAME" && sudo python3 bootstrap.py --port "$PORT"
