---
title: "Argo Inference Service"
category: ai-tools
systems:
  - all
tags:
  - argo
  - argo-shim
  - proxy
  - ssh-tunnel
  - inference
description: >
  Argonne-internal LLM gateway (Argo) — only accessible to Argonne employees.
  Use argo-shim (local proxy + SSH tunnel) to expose apps.inside.anl.gov
  outside the lab network. Load when routing any agent harness through Argo
  from off-site.
last_verified: "2026-11"
---

> **Access note:** This service is **only accessible to Argonne employees** — it requires valid Argonne credentials and either on-site network or the `argo-shim` SSH tunnel described below.

## Purpose

Argo (`apps.inside.anl.gov` / `apps-stage.inside.anl.gov`) is Argonne's internal LLM gateway. From outside the lab network it is not directly reachable. `argo-shim` bridges the gap with a local HTTP proxy plus a reverse SSH tunnel. This skill explains how to discover the shim, how client authentication works, and how to add the Argo endpoint to your harness's model configuration in a harness-agnostic way.

## Prerequisites

- Argonne credentials with access to Argo.
- SSH access to `logins.cels.anl.gov` and `homes.cels.anl.gov` (MFA as required).
- `argo-shim` installed (`pip install argo-shim` or `uvx argo-shim`). Verify with `argo-shim --help`.
- `alcf-tokens` CLI (`pip install alcf-tokens`, then `alcf-tokens login` for Globus) — needed if you also use ALCF Inference.
- Your agent harness installed (Hermes, OpenClaw, etc.) — you will need to locate its model/provider configuration file.

## Key Facts

- **Endpoint outside Argonne:** when off-site, traffic must go through a local shim. The shim typically listens on `http://127.0.0.1:<port>/argoapi` (port is deterministic from your username; check your `ANTHROPIC_BASE_URL` or the shim's startup log — do not hard-code a port from documentation).
- **Discover the live endpoint and port:** do not copy a port from an example. Instead, inspect the shim's runtime state on your host (if it is already running):
  ```bash
  # Is the shim listening, and on which port?
  ss -tlnp | grep argo-shim || lsof -i -P | grep LISTEN | grep argo
  screen -ls | grep argo-shim   # shim usually runs in a screen session
  # The shim writes its URL and token to your Claude settings:
  cat ~/.claude/settings.json | python3 -m json.tool | grep -E "ANTHROPIC_BASE_URL|apiKeyHelper"
  ```
  Use the `ANTHROPIC_BASE_URL` value you find there (e.g., `http://127.0.0.1:12938/argoapi`) and append `/v1` for an OpenAI-compatible base URL.
- **Two different keys — do not confuse them:**
  - *Shim client token:* a random per-run token the shim generates and writes to `~/.claude/settings.json` as `apiKeyHelper: "echo <token>"`. This is what local clients must present to the shim. It changes on each shim restart.
  - *Upstream Argo credential:* the real Argo API key that the shim injects server-side when forwarding to `apps.inside.anl.gov`. Never send this directly to the shim.
- **Token retrieval:** read the live token from settings, do not hard-code it:
  ```bash
  python3 -c "import json;print(json.load(open('$HOME/.claude/settings.json'))['apiKeyHelper'].split()[-1])"
  ```
- **Discover available models — do not hard-code a model list:** Argo's catalog changes over time. Query it live:
  ```bash
  # Via the shim (get a token first as above)
  TOKEN=$(python3 -c "import json;print(json.load(open('$HOME/.claude/settings.json'))['apiKeyHelper'].split()[-1])")
  curl -s http://127.0.0.1:<port>/argoapi/v1/models -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
  # Or via the shim's helper, if available
  argo-shim --help
  ```
  Use the `id` fields returned to choose a model for your harness configuration.
- **Add the endpoint to your harness — honor its config format:** different harnesses store providers differently. Do not copy a Hermes-specific YAML snippet verbatim if you run OpenClaw (or vice versa). Instead:
  1. Locate your harness's model/provider config (e.g., `hermes config path`, `~/.config/openclaw/config.yaml`, etc. — check `your-harness --help` or its docs).
  2. Inspect the existing structure (is it a `providers:` map, a `custom_providers:` list, a `models` array? what keys does it use for URL/auth?).
  3. Add a new entry that mirrors that existing structure, using the live shim URL you discovered, with auth set to a command or env-var reference that reads the shim token (not a pasted static token).

## Examples

### Generic: probe the shim (harness-agnostic)

```bash
# 1. Find the live shim URL and token from the host you are on
ANTHROPIC_BASE_URL=$(python3 -c "import json;print(json.load(open('$HOME/.claude/settings.json'))['env']['ANTHROPIC_BASE_URL'])")
TOKEN=$(python3 -c "import json;print(json.load(open('$HOME/.claude/settings.json'))['apiKeyHelper'].split()[-1])")
echo "Shim at $ANTHROPIC_BASE_URL with token len ${#TOKEN}"

# 2. List live models from Argo via the shim
curl -s "$ANTHROPIC_BASE_URL/v1/models" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20

# 3. OpenAI-compatible chat probe (pick an id from the previous output)
curl -s "$ANTHROPIC_BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"model": "<model-id-from-list>", "messages": [{"role": "user", "content": "Say hello in one word."}]}' \
  | python3 -m json.tool
```

If `curl -I` succeeds but `GET`/`POST` returns `401`, you are presenting the wrong layer's credential — see Pitfalls.

### Harness-specific example: Hermes (illustrative — adapt to your harness)

> For Hermes, `hermes config path` shows the config file. Hermes uses either a modern `providers` map (which honors `key_cmd`) or a legacy `custom_providers` list (where `key_cmd` is ignored on the main turn). Inspect your file first, then add an entry that matches the existing style. Example for a modern `providers` setup:

```yaml
# Example only — first inspect your hermes config and match its existing structure
providers:
  anl-argo:
    base_url: http://127.0.0.1:12938/argoapi/v1  # replace with your live $ANTHROPIC_BASE_URL + /v1
    key_cmd: "python3 -c \"import json;print(json.load(open('$HOME/.claude/settings.json'))['apiKeyHelper'].split()[-1])\""
    api_mode: openai
```

Then verify through the harness:

```bash
hermes chat --provider anl-argo --model <model-id-from-list> "Explain Polaris queue limits in one sentence."
```

For a non-Hermes harness (e.g., OpenClaw), locate its config (check `openclaw --help` or `~/.config/openclaw/`), note whether it expects `api_key`, `key_cmd`, `key_env`, or `extra_headers`, and add the shim URL + token command in that harness's native format — do not paste Hermes YAML verbatim into an OpenClaw config.

## Common Pitfalls

- **Sending the upstream Argo key to the shim → 401.** The shim expects its own per-run token (`apiKeyHelper`), not your Argonne Argo credential. Use the `key_cmd` reading `apiKeyHelper`.
- **Hard-coding the shim token or port.** Both are generated per shim run (port is deterministic per username, token is random per restart). Always read them live as shown above.
- **HEAD succeeds but GET/POST 401s.** The shim exempts `HEAD` from auth for liveness probes. Always verify with `GET /v1/models` or `POST /v1/chat/completions` carrying `Authorization: Bearer`.
- **Wrong config format for your harness.** Pasting a `custom_providers:` snippet into a harness that uses `providers:` (or vice versa) will be silently ignored. Inspect your harness's existing config first.
- **Stale SSH tunnel.** The local proxy may still listen while the reverse tunnel to `homes.cels.anl.gov → apps.inside.anl.gov` is down → `502`/`504` or timeouts. Reattach to `screen -S argo-shim` and check `ssh` logs.

## See Also

- `https://docs.alcf.anl.gov/` — Canonical ALCF documentation
- `https://apps.inside.anl.gov` / `https://apps-stage.inside.anl.gov` — Argo gateway (on-site or via shim off-site)
- `argo-shim --help` and `https://github.com/n-getty/argo-shim` — shim installation and tunnel options
