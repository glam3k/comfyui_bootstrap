# ComfyUI Bootstrap Repo — Conventions

## Purpose
Single-file bootstrap script (`bootstrap.sh`) for deploying ComfyUI on cloud GPU pods (RunPod, Vast.ai, etc.).

## Key Variables (set via env)
- `HF_TOKEN` — Hugging Face token for gated models
- `CIVITAI_API_KEY` — CivitAI API key for model downloads

## Script behavior
- `SKIP_ALL_DOWNLOADS = False` — set `True` to bypass model fetching
- `MAX_WORKERS = 8` — parallel download threads
- Model URLs live in `MODELS_TO_INGEST` dict (per model folder type)
- Custom nodes: VideoHelperSuite + Workflow-Models-Downloader
- SageAttention is built from source (non-fatal if it fails)
- Server launches with `--enable-manager --enable-manager-legacy-ui`

## Running
```bash
sudo python3 bootstrap.py           # run directly
sudo bash -c "$(curl -fsSL <url> | python3)"  # piped from remote
```

## PEP 668 (externally-managed-environment)
The script passes `--break-system-packages` to all pip commands via the `PIP_EXTRA` variable. This is safe for ephemeral cloud instances. On systems where this flag is not needed, change `PIP_EXTRA = ""`.
