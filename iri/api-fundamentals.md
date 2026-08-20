---
title: "IRI API Fundamentals"
category: iri
systems:
  - all
tags:
  - iri
  - api
  - globus
  - authentication
description: >
  How to authenticate to the ALCF IRI API (ALCF Facility API) with a Globus
  token, call its REST endpoints at api.alcf.anl.gov/api/v1, and navigate its
  resources (compute, storage) by UUID. Includes the filesystem API status
  table (implemented vs 501) and the Cloudflare User-Agent pitfall. Load
  before any IRI API interaction.
last_verified: "2026-07"
---

## Purpose

Foundation for all IRI (Integrated Research Infrastructure) API interactions at
ALCF. Covers authentication, the REST endpoint surface, resource UUIDs, the
asynchronous task model, and filesystem API limitations. Load this skill before
any IRI API interaction.

> **This skill targets the ALCF-direct API** (`https://api.alcf.anl.gov/api/v1`),
> as documented at <https://docs.alcf.anl.gov/services/iri-api/>. It does **not**
> use the AmSC (`amsc-client` / `api.american-science-cloud.org`) path. The two
> are different APIs with different auth, endpoints, and request shapes; do not
> mix them.

## Prerequisites

- Python 3.8+
- `pip install globus-sdk`
- An ALCF account (the API authenticates with your ALCF credentials via Globus)

## Key Facts

### Base URL

All endpoints are rooted at:

```
https://api.alcf.anl.gov/api/v1
```

The full OpenAPI specification is at
<https://api.alcf.anl.gov/openapi.json>, and interactive Swagger docs are at
<https://api.alcf.anl.gov/>.

### CRITICAL: Set a non-default User-Agent

`api.alcf.anl.gov` sits behind Cloudflare, which returns **HTTP 403
`{"error":"error code: 1010"}`** when the request `User-Agent` is a default
library string such as `Python-urllib/3.x`. This is a bot-block, *not* an auth
or scope problem — the same valid token succeeds via `curl` and fails via a
default `urllib` UA.

Always send a normal User-Agent header (e.g. `curl/8.x`, `python-requests/2.x`,
or an app-specific string like `alcf-agent/1.0`). The `requests` library sets a
non-default UA by default, so plain `requests` calls work; raw `urllib` needs an
explicit header.

### Authentication

Auth uses a Globus OAuth token obtained with the ALCF auth helper script. There
is a single token for the entire IRI API — the same token is used for
`/compute/*`, `/filesystem/*`, and `/account/*` (despite the underlying scope
being named `filesystem`).

**1. Install the Globus SDK and download the auth script:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install globus-sdk

wget https://raw.githubusercontent.com/argonne-lcf/alcf-facility-api-token/refs/heads/main/alcf_facility_api_globus_token.py
# (or: curl -O <same URL>)
```

**2. Authenticate (one-time, interactive browser step):**

```bash
python alcf_facility_api_globus_token.py authenticate
```

Copy the printed URL into a browser, authenticate with your ALCF credentials
(select "Argonne LCF" and enter your MobilePass+ code), and paste the resulting
authorization code back into the terminal.

**3. Retrieve an access token:**

=== "Bash"

    ```bash
    access_token=$(python alcf_facility_api_globus_token.py get_access_token)
    ```

=== "Python"

    ```python
    from alcf_facility_api_globus_token import get_access_token
    access_token = get_access_token()
    ```

- Access tokens are valid for **48 hours**. `get_access_token` auto-refreshes an
  expired token.
- Refreshed tokens are authorized for up to **7 days**, after which you must
  re-run `authenticate`.
- The token cache lives at
  `~/.globus/app/8b84fc2d-49e9-49ea-b54d-b3a29a70cf31/alcf_facility_api_app/tokens.json`.

Send the token as a Bearer header on every authenticated request:

```
Authorization: Bearer <access_token>
```

Status endpoints (`/status/*`, `/facility`) are **public** and require no token.

### Resource IDs (UUIDs, not names)

The ALCF-direct API addresses resources by **UUID**, not by string name. Fetch
the live map any time from the public endpoint
`GET /api/v1/status/resources`. Current values (verified 2026-07):

| Resource | Type    | UUID                                   | Filesystem paths |
|----------|---------|----------------------------------------|------------------|
| Polaris  | compute | `55c1c993-1124-47f9-b823-514ba3849a9a` | N/A (jobs only)  |
| Crux     | compute | `8b9b42f7-572a-4909-8472-a0453436304c` | N/A (jobs only)  |
| Aurora   | compute | `0325fc07-6fb7-4453-b772-3d5030b2df72` | N/A (jobs only)  |
| Sophia   | compute | `9674c7e1-aecc-4dbb-bf01-c9197e027cd6` | N/A (jobs only)  |
| Home     | storage | `6115bd2c-957a-4543-abff-5fae52992ff2` | `/home`          |
| Eagle    | storage | `1c3ad9d4-2e91-42bc-becb-72b1fde1235c` | `/eagle`, `/lus/eagle` |

Do not hard-code UUIDs blindly in long-lived code; prefer resolving them at
runtime from `/status/resources` and matching on `name`. The table above is for
quick reference and copy-paste examples.

### Compute vs. storage resources

- **Compute** resources (Polaris, Crux, Aurora, ...) accept **job** operations
  (`/compute/*`).
- **Filesystem** operations (`/filesystem/*`) run against **storage** resources
  (Home, Eagle) only. There is no `polaris.fs.*`; filesystem calls take a
  *storage* resource UUID.

### Path constraints (per-identity allowlist)

Filesystem paths must start with an allowed root for the storage resource:

- **Home:** paths must start with `/home`
- **Eagle:** paths must start with `/eagle` or `/lus/eagle`

The API also enforces a **per-identity allowlist**: you can only reach paths
your token's identity is authorized for (e.g. your own `/home/<username>`). A
violation returns an `Input validation error` naming the allowed roots.

### Asynchronous task model

All `/filesystem/*` operations are **asynchronous**: the call returns a
**task ID**, and you poll `GET /api/v1/task/{task_id}` until the task
completes, then read its result. `/compute/*` and `/account/*` and `/status/*`
calls are synchronous (they return their payload directly).

### Filesystem API status (implemented vs 501)

Not every filesystem endpoint is implemented server-side. The OpenAPI spec
lists `501` as a *possible* response for all of them, so the spec alone does not
tell you which are live. Verified behavior (2026-07):

| Operation | Endpoint                          | Status | Notes |
|-----------|-----------------------------------|--------|-------|
| ls        | `GET /filesystem/ls/{rid}`        | Working | Directory listing (async) |
| head      | `GET /filesystem/head/{rid}`      | Working | First N **lines** |
| view      | `GET /filesystem/view/{rid}`      | Working | `size` **bytes** from `offset` |
| mkdir     | `POST /filesystem/mkdir/{rid}`    | Working | `parent: true` makes parents |
| rm        | `DELETE /filesystem/rm/{rid}`     | Working | Deletes file or directory |
| chmod     | `PUT /filesystem/chmod/{rid}`     | Working | Octal `mode` string |
| chown     | `PUT /filesystem/chown/{rid}`     | Working | `owner` / `group` |
| tail      | `GET /filesystem/tail/{rid}`      | **501** | Use `view` and slice instead |
| stat      | `GET /filesystem/stat/{rid}`      | **501** | — |
| checksum  | `GET /filesystem/checksum/{rid}`  | **501** | — |
| upload    | `POST /filesystem/upload/{rid}`   | **501** | No direct upload; write via a job |
| download  | `GET /filesystem/download/{rid}`  | **501** | No direct download; read via `view`/`head` |
| cp/mv/compress/extract/symlink | (POST endpoints) | Unverified | Exist in spec; test before relying on them |

## Examples

### List all resources (public, no auth)

=== "cURL"

    ```bash
    curl -X GET "https://api.alcf.anl.gov/api/v1/status/resources" \
         -H "User-Agent: alcf-agent/1.0"
    ```

=== "Python"

    ```python
    import requests
    r = requests.get("https://api.alcf.anl.gov/api/v1/status/resources")
    r.raise_for_status()
    for res in r.json():
        print(res["name"], res["id"], res.get("resource_type"), res.get("current_status"))
    ```

### List a directory on Eagle (authenticated, async)

```python
import time
import requests
from alcf_facility_api_globus_token import get_access_token

BASE = "https://api.alcf.anl.gov/api/v1"
EAGLE = "1c3ad9d4-2e91-42bc-becb-72b1fde1235c"
headers = {"Authorization": f"Bearer {get_access_token()}"}

# 1. Kick off the async filesystem op -> returns a task id
r = requests.get(f"{BASE}/filesystem/ls/{EAGLE}",
                 params={"path": "/eagle/<your-project>"}, headers=headers)
r.raise_for_status()
task_id = r.json()["id"]          # task handle

# 2. Poll the task until it finishes
while True:
    t = requests.get(f"{BASE}/task/{task_id}", headers=headers).json()
    if t.get("status") in ("completed", "failed", "error"):
        break
    time.sleep(1)

# 3. Read the result (ls entries live under result.output)
print(t["result"]["output"])
```

## Common Pitfalls

- **HTTP 403 `error code: 1010`** — Cloudflare bot-block from a default
  User-Agent. Set a normal UA header. This is *not* an auth failure.
- **Calling filesystem ops with a compute resource UUID.** `/filesystem/*` needs
  a **storage** resource (Home/Eagle). Use the storage UUID.
- **Paths not starting with `/home`, `/eagle`, or `/lus/eagle` are rejected**,
  as are paths outside your identity's allowlist.
- **`tail` returns 501.** Use `view` and slice the returned content.
- **Forgetting the async poll.** `/filesystem/*` returns a task id, not the
  result — you must poll `GET /task/{task_id}`.
- **First auth run requires an interactive browser.** Cannot be automated
  headless without pre-cached tokens (mount the tokens file into containers).
- **`IdentityMismatchError`** — the token cache was created under a different
  Globus identity. Delete
  `~/.globus/app/8b84fc2d-49e9-49ea-b54d-b3a29a70cf31/alcf_facility_api_app/tokens.json`
  and re-run `authenticate`.

## See Also

- `job-submission.md` -- Submitting, listing, and cancelling PBS jobs via the IRI API
- `output-retrieval.md` -- Reading job stdout/stderr after completion
- ALCF IRI API docs: <https://docs.alcf.anl.gov/services/iri-api/>
- OpenAPI spec: <https://api.alcf.anl.gov/openapi.json>
