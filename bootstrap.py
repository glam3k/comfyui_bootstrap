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
    "checkpoints": [],
    "diffusion_models": [],
    "vae": [],
    "loras": []
}

PLUGINS = [
    ("ComfyUI-Manager", "https://github.com/ltdrdata/ComfyUI-Manager.git", None),
    ("SageAttention", "https://github.com/thu-ml/SageAttention.git", "sageattention"),
    ("ComfyUI-VideoHelperSuite", "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git", None),
    ("ComfyUI-Workflow-Models-Downloader", "https://github.com/slahiri/ComfyUI-Workflow-Models-Downloader.git", None),
    ("ComfyUI-Model-Installer", "https://github.com/arleckk/ComfyUI-Model-Installer.git", None),
]


def run_cmd(cmd, cwd=None, env_update=None, check=False):
    print(f"Running: {cmd}")
    current_env = os.environ.copy()
    if env_update:
        current_env.update(env_update)
    result = subprocess.run(cmd, shell=True, cwd=cwd, env=current_env)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def run_cmd_list(cmd_list, cwd=None, env_update=None):
    current_env = os.environ.copy()
    if env_update:
        current_env.update(env_update)
    return subprocess.run(cmd_list, cwd=cwd, env=current_env, capture_output=True)


def check_sudo():
    if os.geteuid() != 0:
        print("Error: This script requires sudo privileges. Run with 'sudo python3 bootstrap.py'")
        sys.exit(1)


def ensure_venv():
    if not os.path.exists(VENV_DIR):
        run_cmd("python3 -m venv .venv")
        print("Virtual environment created at .venv")
    else:
        print("Virtual environment .venv already exists")


def pip_install(pkg, cwd=None):
    run_cmd(f"{VENV_PIP} install {pkg}", cwd=cwd, check=True)


def check_package_installed(package):
    return run_cmd_list([VENV_PYTHON, "-c", f"import {package}"]).returncode == 0


def ensure_git_repo(name, url, target_dir, env_update=None):
    if not os.path.exists(target_dir):
        print(f"Cloning {name}...")
        run_cmd(f"git clone --depth 1 {url} {target_dir}", env_update=env_update, check=True)
    else:
        print(f"{name} already cloned")


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


def fix_permissions():
    original_user = os.environ.get("SUDO_USER") or os.environ.get("USER", "")
    if original_user and original_user != "root":
        run_cmd(f"chown -R {original_user}:{original_user} {ROOT_DIR}")
        print(f"Permissions fixed for user: {original_user}")


def install_plugin(plugin_entry):
    name, url, package_name = plugin_entry
    if name == "SageAttention":
        if check_package_installed("sageattention"):
            print(f"{name} already installed.")
            return
        target_dir = os.path.join(ROOT_DIR, name)
        ensure_git_repo(name, url, target_dir)
        compilation_env = {
            "EXT_PARALLEL": "4",
            "NVCC_APPEND_FLAGS": "--threads 8",
            "MAX_JOBS": "32"
        }
        try:
            run_cmd(f"{VENV_PYTHON} setup.py install", cwd=target_dir, env_update=compilation_env, check=True)
            print(f"{name} installed.")
        except Exception as e:
            print(f"{name} build failed (non-fatal): {e}")
    else:
        target_dir = os.path.join(COMFY_DIR, "custom_nodes", name)
        ensure_git_repo(name, url, target_dir)
        req_file = os.path.join(target_dir, "requirements.txt")
        if os.path.exists(req_file):
            pip_install("-r requirements.txt", cwd=target_dir)


def main():
    print("Bootstrapping ComfyUI environment...")

    check_sudo()
    ensure_venv()

    run_cmd("apt-get update && apt-get install -y git wget curl build-essential python3-venv", check=True)
    pip_install("-U pip ninja wheel setuptools 'huggingface_hub[cli]'")

    if HF_TOKEN:
        os.environ["HF_TOKEN"] = HF_TOKEN
        try:
            run_cmd(f"huggingface-cli login --token {HF_TOKEN}")
            print("HF CLI authenticated.")
        except Exception as e:
            print(f"HF login failed (non-fatal): {e}")

    if not os.path.exists(COMFY_DIR):
        run_cmd(f"git clone https://github.com/comfyanonymous/ComfyUI.git {COMFY_DIR}", check=True)
    pip_install("-r requirements.txt", cwd=COMFY_DIR)

    manager_reqs = os.path.join(COMFY_DIR, "manager_requirements.txt")
    if os.path.exists(manager_reqs):
        pip_install("-r manager_requirements.txt", cwd=COMFY_DIR)

    custom_nodes_path = os.path.join(COMFY_DIR, "custom_nodes")
    os.makedirs(custom_nodes_path, exist_ok=True)

    for plugin in PLUGINS:
        try:
            install_plugin(plugin)
        except Exception as e:
            print(f"Failed to install {plugin[0]}: {e}")

    if CIVITAI_API_KEY:
        manager_config_dir = os.path.join(COMFY_DIR, "custom_nodes", "ComfyUI-Manager")
        os.makedirs(manager_config_dir, exist_ok=True)
        try:
            with open(os.path.join(manager_config_dir, "civitai_token.txt"), "w") as f:
                f.write(CIVITAI_API_KEY.strip())
            print("Civitai token written.")
        except Exception as e:
            print(f"Failed to write Civitai token: {e}")

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

    fix_permissions()

    print("Setup complete. Launching ComfyUI...")
    launch_args = "--listen --port 8188 --enable-manager --enable-manager-legacy-ui"
    if check_package_installed("sageattention"):
        launch_args += " --use-sage-attention"
    run_cmd(f"{VENV_PYTHON} main.py {launch_args}", cwd=COMFY_DIR)


if __name__ == "__main__":
    main()