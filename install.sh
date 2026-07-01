#!/bin/bash

# ComfyUI Bootstrap Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/glam3k/comfyui_bootstrap/main/install.sh | bash -s -- [port]

PORT=${1:-8188}
REPO_URL="https://github.com/glam3k/comfyui_bootstrap.git"
DIR_NAME="comfyui_bootstrap"

echo "Starting ComfyUI Bootstrap installation..."

# Install git if not present
if ! command -v git &> /dev/null; then
    echo "Installing git..."
    sudo apt-get update && sudo apt-get install -y git
fi

# Clone the repository
if [ ! -d "$DIR_NAME" ]; then
    echo "Cloning bootstrap repository..."
    git clone "$REPO_URL" "$DIR_NAME"
fi

# Execute the bootstrap script
echo "Running bootstrap script on port $PORT..."
cd "$DIR_NAME" && sudo python3 bootstrap.py --port "$PORT"
