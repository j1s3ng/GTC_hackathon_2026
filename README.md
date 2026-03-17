# ReliefRoute CA

`ReliefRoute` is an offline-first disaster recovery assistant built to help survivors quickly find relevant support services after wildfires, earthquakes, and other emergencies.

It uses NVIDIA Nemotron to turn natural-language chat into a structured recovery profile, infer the user's state and urgent needs, and surface grounded state and federal resources. The system is designed for real disaster conditions: it supports all 50 states, separates federal and state resource databases, caches official resource pages for local use, and can run either with an online Nemotron backend or a fully local model setup. Its goal is to reduce confusion during crisis by helping people understand what aid may be relevant, what information or documents they may need, and what steps to take next.

It is designed as a hackathon MVP that can:

- intake a survivor's situation
- map urgent needs to recovery steps
- surface relevant state and federal resources
- primarily use NVIDIA Nemotron Super online
- switch to a downloaded local Nemotron model through LM Studio
- cache website snapshots locally when you have connectivity

## Why this project

People affected by wildfire and earthquake events often need help across several systems at once: evacuation, shelter, insurance, food, replacement documents, and public benefits. The point of this MVP is to reduce that overload and turn a stressful situation into a short list of practical next actions.

## Why this is different

Many disaster support tools are region-specific or tied to a single incident. `ReliefRoute` is designed to be broader and more resilient:

- supports all 50 states at the state-agency level, instead of only one city or one disaster region
- separates state and federal resource links clearly
- can infer the survivor's state from ZIP code locally
- works offline with a local resource database and local RAG workflow
- can switch between NVIDIA Nemotron Super online and a fully local Nemotron model for degraded-connectivity conditions

Today, California has the deepest built-in resource coverage, while the broader 50-state support is already in place through the local state emergency management directory and federal resource set.

## What the prototype does

- supports natural disaters and other disasters
- prioritizes immediate safety concerns
- creates a 24-hour recovery checklist
- recommends relevant state/local resources and federal resources in separate lists
- shows what information and documents each service will likely ask for
- can build separate local SQLite RAG databases for federal and state resources to reduce retrieval noise
- works fully offline with bundled resource data
- can cache recommended resource pages to disk for offline reuse
- defaults to NVIDIA Nemotron Super for online reasoning
- can switch to a downloaded Nemotron running in LM Studio on your laptop
- includes an offline state directory for all 50 states plus federal services
- can infer state from ZIP code locally using a built-in ZIP prefix map

## Quick start

Run the built-in demo profile:

```bash
python3 the_beginning.py
```

Run the guided prompt:

```bash
python3 the_beginning.py --interactive
```

Use a JSON input file:

```bash
python3 the_beginning.py --profile-json profile.json
```

Use NVIDIA Nemotron Super online:

```bash
export NVIDIA_API_KEY=your_key_here
python3 the_beginning.py --use-online-nemotron
```

Switch to downloaded local Nemotron through LM Studio:

```bash
python3 the_beginning.py --use-local-nemotron --local-model your-local-nemotron-name
```

LM Studio usually exposes an OpenAI-compatible server at `http://127.0.0.1:1234/v1`.
Download a Nemotron model inside LM Studio first, load it, start the local server, and pass the exact local model name if needed. Local mode does not require an API key.

Refresh cached website snapshots when you have internet:

```bash
export NVIDIA_API_KEY=your_key_here
python3 the_beginning.py --refresh-cache
```

That cache refresh path fetches the latest resource pages and uses online Nemotron Super to create compact offline summaries when an NVIDIA API key is available.

If you store `NVIDIA_API_KEY` in a local `.env` file, `.gitignore` now excludes it from git.

Build a local RAG database from free web fetches and cached pages:

```bash
python3 the_beginning.py --build-rag-db
```

Query the local RAG databases:

```bash
python3 the_beginning.py --rag-query "What documents do I need for FEMA and shelter?"
python3 the_beginning.py --rag-query "What documents do I need for FEMA?" --rag-scope federal
python3 the_beginning.py --rag-query "What state help exists for wildfire?" --rag-scope state
```

The app now creates a separate federal RAG and a per-state RAG. This keeps retrieval narrower and helps reduce hallucination by limiting mixed state/federal context.

By default, the Nemotron path is now strict about grounding:

- it expects both the federal RAG and the selected state RAG to exist
- it retrieves scoped evidence from both before sending a prompt to Nemotron
- if grounded evidence is missing, it falls back to the deterministic local planner instead of sending an ungrounded model request

You can override that with:

```bash
python3 the_beginning.py --use-local-nemotron --allow-ungrounded-model
```

That override is not recommended for disaster guidance.

Use ZIP code to infer state locally:

```bash
python3 the_beginning.py --zipcode 94103
```

Override the state directly if needed:

```bash
python3 the_beginning.py --state-code NY --zipcode 10001
```

The local resource database now includes federal links plus an official state emergency management resource for all 50 states. California still has the richest built-in state-specific extras.

## Web UI

There is also a local browser chat UI in [index.html](/Users/jiseng/VSC/GTC_hackathon_2026/webui/index.html).

It:

- runs locally in the browser
- loads federal and state resource databases from local JSON files
- infers ZIP code, state, disaster type, and victim needs from user chat prompts
- starts with a canned opener that gathers the core recovery facts needed for triage

Serve the repo locally and open `webui/`:

```bash
cd GTC_hackathon_2026
python3 -m http.server
```

## Hugging Face Space

A Hugging Face Docker Space bundle is prepared in [hf_space](/Users/jiseng/VSC/GTC_hackathon_2026/hf_space).

It includes:

- [README.md](/Users/jiseng/VSC/GTC_hackathon_2026/hf_space/README.md) with Space metadata
- [Dockerfile](/Users/jiseng/VSC/GTC_hackathon_2026/hf_space/Dockerfile) for hosting the local backend and Web UI

To deploy it, create a new Docker Space on Hugging Face and upload the contents of `hf_space/` plus:

- [local_server.py](/Users/jiseng/VSC/GTC_hackathon_2026/local_server.py)
- the [webui](/Users/jiseng/VSC/GTC_hackathon_2026/webui) folder
- the [data](/Users/jiseng/VSC/GTC_hackathon_2026/data) folder

Then set `HF_TOKEN` in the Space secrets.

Read only from cache:

```bash
python3 the_beginning.py --show-cache-only
```

Use a custom cache folder:

```bash
python3 the_beginning.py --cache-dir ./cache --refresh-cache
```

## Example JSON profile

```json
{
  "disaster_type": "earthquake",
  "county": "Alameda County",
  "situation": "The apartment building has cracks and we are staying with friends.",
  "housing_damage": "major damage",
  "insurance_status": "insured",
  "household_size": 3,
  "has_medical_need": false,
  "has_mobility_need": true,
  "needs_shelter": false,
  "needs_food": true,
  "needs_documents": false,
  "needs_pet_help": false,
  "income_disrupted": true,
  "safe_now": true
}
```

## Demo framing for the hackathon

Pitch it as an AI recovery copilot for disaster survivors after earthquakes and wildfires:

1. A user describes their disaster situation in plain English.
2. The app structures the case into risk, needs, and likely next steps.
3. NVIDIA Nemotron Super produces a calm, personalized action plan grounded in trusted resources and cached reference material.

## Next upgrades

- county-specific resource packs
- multilingual output
- eligibility triage for disaster benefits
- SMS or voice intake
- document checklist generation by aid program

## Offline-first workflow

1. Run the app offline and use the built-in local resource database.
2. When internet is available, run `--refresh-cache` to store local snapshots of recommended resource pages.
3. Use `--use-online-nemotron` for the default Nemotron Super path.
4. Switch to `--use-local-nemotron` when you want fully local inference in LM Studio.

## Nemotron guardrails

- The app validates that both online and local model names contain `nemotron`.
- The local mode also validates that the API base URL is local, such as `127.0.0.1` or `localhost`.
- This keeps the demo aligned with Nemotron Super online and Nemotron locally.
