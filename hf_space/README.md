---
title: ReliefRoute
emoji: 🚑
colorFrom: orange
colorTo: green
sdk: docker
app_port: 7860
pinned: false
models:
  - nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16
---

# ReliefRoute

ReliefRoute is a local-first disaster recovery chat for finding relevant support services.

This Space serves:

- a browser chat UI
- a lightweight local backend
- Hugging Face Nemotron Super as the default model backend
- LM Studio fallback when configured elsewhere

## Required Space Secret

Set this in your Hugging Face Space Settings:

- `HF_TOKEN`

## Optional Variables

- `HF_MODEL=nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16`
- `RELIEFROUTE_HOST=0.0.0.0`
- `RELIEFROUTE_PORT=7860`

## Notes

- This is configured as a Docker Space so the token stays server-side.
- The web UI and local databases are served from the same backend.
