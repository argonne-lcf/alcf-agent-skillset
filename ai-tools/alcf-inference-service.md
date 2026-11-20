---
title: "ALCF Inference Service"
category: ai-tools
systems:
  - all
tags:
  - alcf-inference-service
  - inference
  - llm
  - openai-api
  - globus-auth
description: >
  Use the ALCF Inference Service (Cloudflare-hosted OpenAI-compatible API) from
  any harness. Covers discovering live endpoints/models, Globus token auth via
  alcf-tokens, and adding the service to your harness's model configuration.
  Load when routing any agent harness through ALCF-hosted models.
last_verified: "2026-11"
---

## Purpose

The ALCF Inference Service exposes OpenAI-compatible LLM inference behind a Cloudflare gateway reachable from any network (no VPN/shim required). This skill tells any agent — Hermes, OpenClaw, or other — how to discover the current endpoints and models, obtain a Globus token, and add the service to its own harness configuration by honoring that harness's config format.

## Prerequisites

- An ALCF account with Globus Auth linked to the `inference` scope.
- `alcf-tokens` CLI (`pip install alcf-tokens`; run `alcf-tokens login` for initial Globus browser flow; provides `get-token`, `test-token`, `list-services`).
- Network egress to `https://inference-api.alcf.anl.gov` (public Cloudflare endpoint).
- Your agent harness installed — you will need to locate its model/provider config file.

## Key Facts

- **Base URL pattern (verify live, do not hard-code from docs):** `https://inference-api.alcf.anl.gov/.../api/v1` — fronted by Cloudflare, reachable from any network. The exact path suffix varies by resource (e.g., `/resource_server/<name>/api/v1` vs `/<name>/vllm/v1` for some hosts). Always confirm the current path by querying live rather than copying a table.
- **Discover available services and models — do not hard-code a model list:**
  ```bash
  # 1. Which resource servers exist right now?
  alcf-tokens list-services
  # 2. For each base URL you intend to use, list its current models:
  TOKEN=$(alcf-tokens get-token inference)
  curl -s https://inference-api.alcf.anl.gov/resource_server/<name>/api/v1/models \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
  # If /models 404s, try the alternate suffix noted for that resource (e.g., /vllm/v1)
  ```
  Model IDs and availability change over time — use the `id` fields returned above when configuring your harness, not a table copied from documentation. A known primary example is `muse-spark-bf16` (historically on Minerva/Tara), but always verify it still appears in the live list before use.
- **Auth — Globus token via `alcf-tokens` CLI:** tokens are obtained with `alcf-tokens get-token inference`, are ~91 characters, and can be validated with `alcf-tokens test-token inference`. Send as `Authorization: Bearer $TOKEN`. Tokens expire — re-mint with `get-token` as needed.
- **Add the endpoint to your harness — honor its config format:** harnesses store providers differently (Hermes `custom_providers` list vs `providers` map, OpenClaw `models` array, etc.). Do not paste a Hermes YAML snippet into an OpenClaw config (or vice versa). Instead:
  1. Locate your harness's config file (e.g., `hermes config path`, `~/.config/openclaw/config.yaml`, or `your-harness --help`).
  2. Inspect its existing entries to learn which keys it honors for URL/auth (`base_url`/`url`/`api`, `key_env`/`api_key`/`key_cmd`, `api_mode`, `models`).
  3. Add a new entry that mirrors that existing style, using the live base URL and model IDs you discovered above, and referencing your token via an env-var or command reference — not a pasted static token.
  4. Ensure your harness process inherits the env var (see Pitfalls).

## Examples

### 1. Discover live services and models (harness-agnostic)

```bash
# Which services are configured in alcf-tokens?
alcf-tokens list-services

# Mint a token and list models for a candidate endpoint
TOKEN=$(alcf-tokens get-token inference)
echo "token len ${#TOKEN} (expect ~91)"

for base in \
  https://inference-api.alcf.anl.gov/resource_server/tara/api/v1 \
  https://inference-api.alcf.anl.gov/resource_server/minerva/api/v1 \
  https://inference-api.alcf.anl.gov/resource_server/metis/api/v1 \
  https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1; do
  echo "--- $base ---"
  curl -s "$base/models" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json;d=json.load(sys.stdin);print([m['id'] for m in d.get('data',[])][:5])"
done
```

Use the discovered `id` values as the model names in your harness config — do not invent or copy stale IDs.

### 2. Generic curl smoke test (any harness)

```bash
TOKEN=$(alcf-tokens get-token inference)
# Pick a base_url and model id from the discovery step above
BASE=https://inference-api.alcf.anl.gov/resource_server/tara/api/v1
MODEL=muse-spark-bf16  # replace with an id you actually saw in /models

curl -s "$BASE/chat/completions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"Say hello in one sentence.\"}]}" \
  | python3 -m json.tool
```
A `401` here means your token is expired or missing; a `404` for `/models` or the model id means you used a stale path/id — re-discover.

### 3. Harness-specific example: Hermes (illustrative — adapt to your harness)

> For Hermes, inspect your config first (`hermes config get custom_providers` or `hermes config get providers`). Hermes honors `key_env` pointing to an env var on the legacy `custom_providers` list form. Example adapting the discovered values:

```yaml
# Example only — inspect your Hermes config and match its existing style
custom_providers:
  - name: alcf-tara
    base_url: https://inference-api.alcf.anl.gov/resource_server/tara/api/v1  # from discovery
    api_mode: openai
    key_env: ALCF_IS_KEY   # env var holding the alcf-tokens token
    models:
      muse-spark-bf16: {}
```

```bash
export ALCF_IS_KEY="$(alcf-tokens get-token inference)"
# Verify Hermes will see it, then chat — use a model id you discovered:
hermes chat --model muse-spark-bf16 --provider custom:alcf-tara "Hello in one sentence."
```

For another harness (e.g., OpenClaw), find its config file, note its URL/auth keys (check existing entries), and add the discovered `base_url` + model id + env-var reference in that harness's native format.

### 4. Refreshing an expired token

```bash
alcf-tokens get-token inference --force  # or without --force; complete Globus flow if prompted
export ALCF_IS_KEY="$(alcf-tokens get-token inference)"
# Restart your harness process so it inherits the new env
# (harness-specific: pkill -f hermes; hermes serve &  or  openclaw restart, etc.)
```

## Common Pitfalls

- **Hard-coding a model table from docs.** Endpoints and model IDs rotate. If you get `model not found` or `404` for `/models`, re-run discovery — do not debug your harness config.
- **`curl` succeeds but harness returns `401`.** Your harness process does not have the env var in its inherited environment. Confirm `echo ${#ALCF_IS_KEY}` is ~91 in the shell that launched the harness, then restart that harness process.
- **Using `ALCF_API_KEY` instead of the env var your harness honors.** Check your harness's existing entries — for Hermes's legacy `custom_providers` it is `ALCF_IS_KEY`. Copying the wrong var name silently yields no auth.
- **Pasting a static token into config.** Tokens expire (typically ~hours). Reference an env var or command, not a literal 91-char string.
- **Mixing harness config formats.** Pasting a `custom_providers:` snippet into a harness that uses `providers:` (or `models:`) will be ignored. Inspect first.

## See Also

- ALCF Inference Service gateway: `https://inference-api.alcf.anl.gov` (try `/models` on each base URL)
- `alcf-tokens --help` (subcommands: `login`, `get-token`, `test-token`, `list-services`)
- Your harness docs (e.g., `hermes config --help`, `openclaw --help`) to locate the correct config file and provider schema
