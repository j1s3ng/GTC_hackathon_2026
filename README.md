# ReliefRoute

`ReliefRoute` is a disaster recovery copilot that uses NVIDIA Nemotron plus grounded retrieval over official disaster resources.

In the demo, a survivor describes what happened in plain language. ReliefRoute infers state and urgent needs, retrieves matching federal and state resources from a local resource layer, and uses Nemotron to generate a grounded recovery response. The same Web UI can run with Bitdeer-hosted Nemotron Super, auto-fallback to local LM Studio Nemotron, or switch to local-only mode for privacy.

## Demo Version

This is the tech-demo framing of the project:

- chat-first Web UI for live demos
- Nemotron-powered response generation
- RAG-style retrieval from local federal and per-state resource databases
- clear federal vs state resource separation
- auto routing between Bitdeer Nemotron Super and local LM Studio Nemotron
- local-only toggle for privacy-sensitive use
- built-in scraper/cache tool for refreshing official resource text
- cached official resources for offline or degraded-connectivity scenarios

## What Makes It Different

- supports all 50 states instead of a single city or incident
- separates federal and state retrieval to reduce hallucination
- infers state from ZIP code or free-form user chat
- keeps the resource layer refreshable and separate from the model layer
- can run online, auto-fallback, or fully local from the same interface

## Core Flow

1. User describes the disaster in chat.
2. ReliefRoute infers location, disaster type, and urgent needs.
3. The app retrieves relevant federal and state resources from local databases.
4. A resource lookup tool can refresh official pages when online and falls back to cached text when offline.
5. Nemotron generates a grounded response using that structured evidence.
6. The UI can show which backend answered: Bitdeer, LM Studio, or local planner fallback.

## Quick Start

### Web UI

The main demo surface is the local browser chat in [index.html](/Users/jiseng/VSC/GTC_hackathon_2026/webui/index.html), served by [local_server.py](/Users/jiseng/VSC/GTC_hackathon_2026/local_server.py).

It is designed to:

- run locally on your machine
- infer state, needs, and recovery profile from plain-language chat
- use NVIDIA Nemotron Super through Bitdeer when online credentials are available
- automatically fall back to local LM Studio Nemotron if the online backend is unavailable
- let privacy-sensitive users force local-only inference from the chat UI toggle
- keep retrieval, grounding, and backend routing visible enough for a technical demo

Setup:

Create a local `.env` from [`.env.example`](/Users/jiseng/VSC/GTC_hackathon_2026/.env.example), then run:

```bash
cd GTC_hackathon_2026
python3 local_server.py
```

Open:

```text
http://127.0.0.1:8000/webui/
```

The Web UI backend flow is:

- `BITDEER_API_KEY` present: try Bitdeer-hosted NVIDIA Nemotron Super first
- if online inference fails: fall back to local LM Studio Nemotron at `http://127.0.0.1:1234/v1`
- if both model backends fail: fall back to local structured planner logic
- for grounding, the backend runs a resource lookup tool that prefers fresh web fetches when asked to refresh and otherwise falls back to cached resource text or local metadata

This gives the demo three modes:

- `Auto`: Bitdeer first, then LM Studio fallback
- `Online`: force Bitdeer-hosted Nemotron Super
- `Local`: force LM Studio for privacy and fully local inference

Typical `.env` values:

```env
BITDEER_API_KEY=your_bitdeer_api_key_here
BITDEER_MODEL=nvidia/NVIDIA-Nemotron-3-Super-120B-A12B
LM_STUDIO_MODEL=nemotron
LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1
RELIEFROUTE_HOST=127.0.0.1
RELIEFROUTE_PORT=8000
```

## Architecture Snapshot

- `webui/`: chat-first browser interface
- [local_server.py](/Users/jiseng/VSC/GTC_hackathon_2026/local_server.py): local backend with Bitdeer, LM Studio, and fallback routing
- [data/federal_resources.json](/Users/jiseng/VSC/GTC_hackathon_2026/data/federal_resources.json): federal resource database
- [data/states](/Users/jiseng/VSC/GTC_hackathon_2026/data/states): per-state local resource databases
- [resource_tools.py](/Users/jiseng/VSC/GTC_hackathon_2026/resource_tools.py): scraper, cache, and retrieval tool layer used by the AI backend
- [refresh_resource_cache.py](/Users/jiseng/VSC/GTC_hackathon_2026/scripts/refresh_resource_cache.py): manual cache refresh/query script
- `cache/`: offline snapshots of official resource pages, ignored by git
- local JSON resource data keeps the demo fast and portable

## Resource Tool

The AI backend now has a built-in resource tool:

- it can scrape official resource pages and cache the cleaned text locally
- it can retrieve relevant snippets for the current chat prompt
- it falls back to cache when the network is unavailable
- if no cache exists, it falls back again to bundled local resource metadata

Manual refresh/query examples:

```bash
python3 scripts/refresh_resource_cache.py --state-code CA --refresh
python3 scripts/refresh_resource_cache.py --state-code CA --query "What documents do I need for FEMA and shelter?"
```

## Demo framing for the hackathon

Pitch it as a grounded disaster recovery copilot:

1. A user describes their disaster situation in plain English.
2. The app infers state and needs, then retrieves matching federal and state resources.
3. NVIDIA Nemotron uses that evidence to generate a grounded response instead of guessing from model memory.
4. The same chat can auto-fallback to local inference or switch to full local mode for privacy.

## Next upgrades

- refreshable cache and rebuild tooling for the resource layer
- scoped federal and per-state RAG persistence if the demo grows into a fuller product
- county-specific resource packs
- multilingual output
- eligibility triage for disaster benefits
- SMS or voice intake
- document checklist generation by aid program
