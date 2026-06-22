#!/usr/bin/env python3
import os
import sys
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

SKIP_ALL_DOWNLOADS = False
MAX_WORKERS = 8

os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

HF_TOKEN = os.getenv("HF_TOKEN", "")
CIVITAI_API_KEY = os.getenv("CIVITAI_API_KEY", "")

ROOT_DIR = os.getcwd()
COMFY_DIR = os.path.join(ROOT_DIR, "ComfyUI")
VENV_DIR = os.path.join(ROOT_DIR, ".venv")
VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python3")
VENV_PIP = os.path.join(VENV_DIR, "bin", "pip")

MODELS_TO_INGEST = {
    "checkpoints": [
        ("https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors", False),
    ],
    "diffusion_models": [
        ("huggingface-cli download Kijai/WanVideo_comfy InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors --local-dir .", False),
    ],
    "vae": [
        ("https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors", False),
    ],
    "loras": []
}


def run_cmd(cmd, cwd=None, env_update=None):
    print(f"Running: {cmd}")
    current_env = os.environ.copy()
    if env_update:
        current_env.update(env_update)
    subprocess.run(cmd, shell=True, check=True, cwd=cwd, env=current_env)


def ensure_venv():
    if not os.path.exists(VENV_DIR):
        run_cmd("python3 -m venv .venv")
        print("Virtual environment created at .venv")
    else:
        print("Virtual environment .venv already exists")


def pip_install(pkg, cwd=None):
    run_cmd(f"{VENV_PIP} install {pkg}", cwd=cwd)


def download_worker(task):
    folder_type, download_target, skip_flag = task

    if skip_flag:
        print(f"[SKIPPED] Model flag set to True for models/{folder_type}.")
        return

    target_dir = os.path.join(COMFY_DIR, "models", folder_type)
    os.makedirs(target_dir, exist_ok=True)

    try:
        if download_target.startswith("huggingface-cli download"):
            if HF_TOKEN and "--token" not in download_target:
                download_target += f" --token {HF_TOKEN}"
            print(f"[HF] Downloading into models/{folder_type}...")
            run_cmd(download_target, cwd=target_dir)
            print(f"[HF] Completed download into models/{folder_type}")

        else:
            if "civitai.com" in download_target and CIVITAI_API_KEY:
                separator = "&" if "?" in download_target else "?"
                download_target += f"{separator}token={CIVITAI_API_KEY}"

            parsed_url = urllib.parse.urlparse(download_target)
            filename = os.path.basename(parsed_url.path)
            dest_path = os.path.join(target_dir, filename)

            if os.path.exists(dest_path):
                print(f"[EXISTING] {filename} already present in models/{folder_type}.")
                return

            print(f"[DOWNLOADING] {filename} via wget...")
            run_cmd(f"wget -c -q --show-progress -O '{dest_path}' '{download_target}'")
            print(f"[FINISHED] {filename} downloaded.")

    except Exception as e:
        print(f"[WARN] Download failed for models/{folder_type}: {e}")


def main():
    print("Bootstrapping ComfyUI environment...")

    # Step 0: Create virtual environment
    ensure_venv()

    # Step 1: System dependencies
    run_cmd("apt-get update && apt-get install -y git wget curl build-essential python3-venv")
    pip_install("-U pip ninja wheel setuptools 'huggingface_hub[cli]'")

    # Hugging Face login
    if HF_TOKEN:
        os.environ["HF_TOKEN"] = HF_TOKEN
        try:
            run_cmd(f"huggingface-cli login --token {HF_TOKEN}")
            print("HF CLI authenticated.")
        except Exception as e:
            print(f"HF login failed (non-fatal): {e}")

    # SageAttention
    sage_dir = os.path.join(ROOT_DIR, "SageAttention")
    if not os.path.exists(sage_dir):
        print("Building SageAttention...")
        try:
            run_cmd(f"git clone https://github.com/thu-ml/SageAttention.git {sage_dir}")
            compilation_env = {
                "EXT_PARALLEL": "4",
                "NVCC_APPEND_FLAGS": "--threads 8",
                "MAX_JOBS": "32"
            }
            run_cmd(f"{VENV_PYTHON} setup.py install", cwd=sage_dir, env_update=compilation_env)
            print("SageAttention installed.")
        except Exception as e:
            print(f"SageAttention build failed (non-fatal): {e}")

    # Step 2: ComfyUI
    if not os.path.exists(COMFY_DIR):
        run_cmd(f"git clone https://github.com/comfyanonymous/ComfyUI.git {COMFY_DIR}")
    pip_install("-r requirements.txt", cwd=COMFY_DIR)

    manager_reqs = os.path.join(COMFY_DIR, "manager_requirements.txt")
    if os.path.exists(manager_reqs):
        pip_install("-r manager_requirements.txt", cwd=COMFY_DIR)

    # Step 3: Custom nodes
    custom_nodes_path = os.path.join(COMFY_DIR, "custom_nodes")
    os.makedirs(custom_nodes_path, exist_ok=True)

    # Civitai token
    if CIVITAI_API_KEY:
        manager_config_dir = os.path.join(custom_nodes_path, "ComfyUI-Manager")
        os.makedirs(manager_config_dir, exist_ok=True)
        try:
            with open(os.path.join(manager_config_dir, "civitai_token.txt"), "w") as f:
                f.write(CIVITAI_API_KEY.strip())
            print("Civitai token written.")
        except Exception as e:
            print(f"Failed to write Civitai token: {e}")

    # VideoHelperSuite
    vhs_path = os.path.join(custom_nodes_path, "ComfyUI-VideoHelperSuite")
    if not os.path.exists(vhs_path):
        run_cmd("git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git", cwd=custom_nodes_path)
    pip_install("-r requirements.txt", cwd=vhs_path)

    # Workflow Models Downloader
    downloader_node = os.path.join(custom_nodes_path, "ComfyUI-Workflow-Models-Downloader")
    if not os.path.exists(downloader_node):
        run_cmd("git clone https://github.com/slahiri/ComfyUI-Workflow-Models-Downloader.git", cwd=custom_nodes_path)
    pip_install("-r requirements.txt", cwd=downloader_node)

    # Step 4: Model downloads
    if SKIP_ALL_DOWNLOADS:
        print("Global download skip active.")
    else:
        download_tasks = []
        for folder_type, items in MODELS_TO_INGEST.items():
            for download_target, skip_flag in items:
                download_tasks.append((folder_type, download_target, skip_flag))
        if download_tasks:
            print(f"Downloading with {MAX_WORKERS} parallel workers...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                executor.map(download_worker, download_tasks)

    # Step 5: Launch
    print("Setup complete. Launching ComfyUI...")
    launch_args = "--listen 127.0.0.1 --port 8188 --use-sage-attention --enable-manager --enable-manager-legacy-ui"
    run_cmd(f"{VENV_PYTHON} main.py {launch_args}", cwd=COMFY_DIR)


if __name__ == "__main__":
    main()
