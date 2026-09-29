---
title: "ALCF Tokens — One Login for ALCF Services"
name: alcf-tokens
category: software
systems:
  - all
tags:
  - alcf-tokens
  - authentication
  - globus
  - tokens
  - iri
  - globus-compute
  - globus-transfer
  - inference
description: >
  The `alcf-tokens` package (PyPI): a centralized CLI + Python API that mints
  and auto-refreshes Globus tokens for four ALCF services — inference, iri,
  globus-compute, and globus-transfer — from a single browser login. Covers the
  CLI commands, the `alcf_tokens.auth` authorizer functions, transfer-collection
  authorization, the token cache location, and the dependency-free shell script.
  Load whenever you need a token or authorizer for any ALCF service, or before
  the IRI / Globus Compute / Globus Transfer skills.
last_verified: "2026-09"
alcf_docs_url: "https://github.com/argonne-lcf/alcf-tokens"
---

# alcf-tokens — one login for ALCF services

[`alcf-tokens`](https://github.com/argonne-lcf/alcf-tokens) (on PyPI) is the
centralized ALCF client for obtaining Globus access tokens. One `alcf-tokens
login` covers every ALCF service that authenticates with Globus, and the Python
API hands your script a ready-made authorizer that refreshes the stored token as
needed — so you never hand-roll a `NativeAppAuthClient` OAuth flow per service.

## Purpose

This is the auth foundation shared by the IRI, Globus Compute, Globus Transfer,
and Inference skills. Load it when you need to:

- get a Bearer token for the IRI or Inference REST APIs, or
- get a `globus_sdk` / `globus_compute_sdk` authorizer for Transfer or Compute,

without writing a separate device-code / native-app login for each. The
service-specific skills reference this one instead of repeating the auth details.

## Prerequisites

- **Python ≥ 3.10** (hard requirement of the package).
- An ALCF account with a linked Globus identity. The one-time `login` is an
  interactive browser flow (select "Argonne LCF", authenticate with your ALCF
  username + MobilePASS+/CRYPTOCard OTP).
- `globus-sdk` / `globus-compute-sdk` installed only if you use the authorizer
  functions with those SDKs (they are not pulled in for a plain `get-token`).

### Agent usage note

`alcf-tokens login` opens a browser and **cannot be driven headless**. Surface it
to the user to run in their own shell (e.g. `! alcf-tokens login`); the refreshed
tokens land in the shared cache (see Key Facts) and every later `get-token` /
authorizer call in any environment on that machine picks them up non-interactively.

## Key Facts

- **Four services:** `inference`, `iri`, `globus-compute`, `globus-transfer`.
  `alcf-tokens list-services` prints the live list.

- **Install:** `pip install alcf-tokens` (or `uv pip install alcf-tokens`). For a
  throwaway invocation, `uvx alcf-tokens --help` needs no venv.

- **Login once, all services:** `alcf-tokens login`. Re-auth a single service
  with `alcf-tokens login <service>`.

- **Shared token cache (per-user, not per-venv):**
  `~/.globus/app/7f3e61f5-e0de-4e8f-9150-0a62c65dda63/alcf_tokens/tokens.json`
  (Globus client ID `7f3e61f5-e0de-4e8f-9150-0a62c65dda63`, app name
  `alcf_tokens`). Any environment with `alcf-tokens` importable reads the same
  cache, so one login serves every venv/conda env on the machine. Wipe it with
  `alcf-tokens clear-tokens`.

- **Python API (`alcf_tokens.auth`)** — all refresh the stored token as needed
  and raise `alcf_tokens.auth.AuthError` (telling you to run `alcf-tokens login`)
  when there is no valid token:
  - `get_access_token(service)` → raw token **string** (for REST `Authorization:
    Bearer` headers — IRI, Inference).
  - `get_service_authorizer(service)` → a `globus_sdk` authorizer for any service
    (used for Globus Compute `Client(authorizer=...)`).
  - `get_transfer_authorizer([collections])` → authorizer for the Globus Transfer
    API. Pass the **same** collection entries you authorized at login.
  - `get_https_authorizer(collection)` → authorizer for direct HTTPS reads/writes
    on one collection.

- **Transfer needs collections authorized at login.** Because a transfer moves
  data between two collections, authorize **both ends** in one `login` with
  repeated `--authorize-transfer` flags. Scope suffixes (optional, combinable in
  either order):
  - `:data_access` — required for a GCS **mapped** collection (all ALCF DTN
    collections).
  - `:https` — required for direct HTTPS reads/writes rather than a
    collection-to-collection Transfer task.

- **Built-in transfer collection aliases** (each already includes `data_access`):
  `home` (`9032dd3a-e841-4687-a163-2720da731b5b`), `eagle`
  (`05d2c76a-e867-4f67-aa57-76edeb0beda0`), `flare`
  (`f39a7a0f-5bfc-46ce-9615-ba9f8592814f`). Any other collection is authorized by
  its UUID.

- **`test-token` coverage is uneven.** `alcf-tokens test-token iri` (or
  `inference`) returns `{"ready": true, "error": null}` when good. `test-token
  globus-compute` currently reports "not yet implemented" — use `get-token
  globus-compute` (exit 0 with non-empty output) as the presence check instead.

- **Dependency-free shell script** for environments without Python: `alcf-tokens.sh`
  (POSIX `sh`; needs only `curl`, `jq`, `awk`, `openssl`). Supports `inference`,
  `iri`, and `globus-compute` — **not** `globus-transfer`. Mirrors the CLI's
  `<action> [<service>]` form.

## Examples

### Log in and verify

```bash
pip install alcf-tokens
alcf-tokens login                     # all services, one browser flow
alcf-tokens list-services             # inference, iri, globus-compute, globus-transfer
alcf-tokens test-token iri            # -> {"ready": true, "error": null}
```

### REST APIs (IRI, Inference) — a token string

```python
from alcf_tokens.auth import get_access_token
headers = {
    "Authorization": f"Bearer {get_access_token('iri')}",
    "User-Agent": "alcf-agent/1.0",   # IRI also needs a non-default UA (Cloudflare)
}
```

Shell equivalent: `access_token=$(alcf-tokens get-token iri)`.

### Globus Compute — an authorizer-backed Client

```python
from globus_compute_sdk import Client, Executor
from alcf_tokens.auth import get_service_authorizer

gcc = Client(authorizer=get_service_authorizer("globus-compute"))
with Executor(endpoint_id=POLARIS, client=gcc) as gce:
    ...
```

### Globus Transfer — authorize both ends at login, then read them back

```bash
# Authorize BOTH collections the transfer touches, in one login.
alcf-tokens login --authorize-transfer home \
                  --authorize-transfer 05d2c76a-e867-4f67-aa57-76edeb0beda0:data_access
```

```python
import globus_sdk
from alcf_tokens.auth import get_transfer_authorizer
# Same entries you authorized at login, so a missing consent surfaces clearly.
tc = globus_sdk.TransferClient(authorizer=get_transfer_authorizer(["home", "eagle"]))
```

For direct HTTPS on a collection, authorize `<collection>:https` at login and use
`get_https_authorizer(<collection>)`.

## Common Pitfalls

- **`alcf_tokens.auth.AuthError` on any call:** no valid token for that service.
  Run `alcf-tokens login <service>` (or `alcf-tokens login`). Headless code
  cannot recover from this on its own — the login is a browser flow.
- **Package not importable in the running env → silent fallback.** Scripts that
  *prefer* alcf-tokens (e.g. `remote_bash.py`) fall back to the SDK's own cache
  if the import fails. Install it into that venv/conda env, or add it to a
  `uv run --script` inline dependency block.
- **Transfer `ConsentRequired` / opaque Globus error:** you didn't authorize
  that collection at login, or omitted `:data_access` on a mapped collection.
  Re-run `login` with the right `--authorize-transfer <uuid>:data_access`, and
  pass the same entries to `get_transfer_authorizer`.
- **`test-token globus-compute` says "not yet implemented":** expected — that
  service has no test path yet. Use `get-token globus-compute` as the check.
- **Wrong function for the job:** REST APIs want the **string** from
  `get_access_token`; the Globus SDKs want an **authorizer** from
  `get_service_authorizer` / `get_transfer_authorizer`. Mixing them is the most
  common integration error.

## See Also

- `../iri/api-fundamentals.md` — IRI API auth (uses `get_access_token("iri")`)
- `../globus/data-transfer.md` — Globus Transfer (uses `get_transfer_authorizer`)
- `../globus/globus-compute-multiuser-endpoints.md` — Globus Compute (uses
  `get_service_authorizer("globus-compute")`)
- `../remote-bash/SKILL.md` — working example of the alcf-tokens compute path
- alcf-tokens on GitHub: <https://github.com/argonne-lcf/alcf-tokens>
- alcf-tokens on PyPI: <https://pypi.org/project/alcf-tokens/>
