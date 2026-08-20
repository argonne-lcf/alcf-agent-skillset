---
title: "IRI Job Submission"
category: iri
systems:
  - all
tags:
  - iri
  - api
  - job-submission
  - pbs
  - compute
description: >
  How to submit, list, inspect, and cancel PBS jobs through the ALCF IRI API
  (api.alcf.anl.gov) using a Globus Bearer token. Covers the JSON job body
  schema, the resources/attributes fields, and job monitoring. Load when
  submitting jobs via IRI.
last_verified: "2026-07"
---

## Purpose

Guide for submitting and monitoring PBS jobs through the ALCF IRI API. Covers the
job request schema, listing/inspecting/cancelling jobs, and monitoring patterns.

> **ALCF-direct API** (`https://api.alcf.anl.gov/api/v1`). Job submission is a
> plain JSON `POST` — there is **no GraphQL layer and no base64 workaround**.
> This is different from the AmSC (`amsc-client`) path; see `api-fundamentals.md`.

> **Verification note:** the request/response shapes below are taken from the
> ALCF IRI documentation (<https://docs.alcf.anl.gov/services/iri-api/>) and the
> live OpenAPI spec (<https://api.alcf.anl.gov/openapi.json>). The job *submit*,
> *cancel*, and *update* flows in this skill are **doc/spec-derived and have not
> been live-tested**; read-only status/list flows have. Treat submit/cancel as
> authoritative-per-docs but confirm against a real job before depending on exit
> semantics.

## Prerequisites

- A valid IRI access token (see `api-fundamentals.md`)
- An ALCF allocation with a valid project account
- The target compute resource UUID (e.g. Polaris `55c1c993-1124-47f9-b823-514ba3849a9a`)

## Key Facts

### Endpoints

| Action | Method & Path |
|--------|---------------|
| Submit a job | `POST /api/v1/compute/job/{resource_id}` |
| Update a job | `PUT /api/v1/compute/job/{resource_id}/{job_id}` |
| List jobs | `POST /api/v1/compute/status/{resource_id}` |
| Get one job | `GET /api/v1/compute/status/{resource_id}/{job_id}` |
| Cancel a job | `DELETE /api/v1/compute/cancel/{resource_id}/{job_id}` |

Currently supported compute resources for job submission: **Polaris** and
**Crux** (per the ALCF docs). Send `Authorization: Bearer <token>` and, for POST
bodies, `Content-Type: application/json`.

### Job request body schema

`POST /compute/job/{resource_id}` takes a JSON body. Key fields (from the
OpenAPI `Job` schema):

| Field | Type | Description |
|-------|------|-------------|
| `executable` | str | Path to executable, e.g. `/bin/bash` |
| `arguments` | list[str] | Arguments to the executable |
| `directory` | str | Working directory on the compute node |
| `name` | str | Job name |
| `stdout_path` | str | Directory (or file) for stdout |
| `stderr_path` | str | Directory (or file) for stderr |
| `environment` | dict | Environment variables |
| `resources` | object | `ResourceSpec` (see below) |
| `attributes` | object | `JobAttributes` (see below) |
| `pre_launch` / `post_launch` | str | Commands run before/after the executable (exist in the ALCF schema; verify before relying on them) |

**`resources` (ResourceSpec):** `node_count`, `process_count`,
`processes_per_node`, `cpu_cores_per_process`, `gpu_cores_per_process`,
`exclusive_node_use` (default `true`), `memory`.

**`attributes` (JobAttributes):**

| Field | Type | Description |
|-------|------|-------------|
| `duration` | int | Wall time in **SECONDS** |
| `queue_name` | str | PBS queue name |
| `account` | str | Project allocation to charge |
| `reservation_id` | str | Optional reservation |
| `custom_attributes` | dict | Passthrough PBS attributes, e.g. `{"filesystems": "home:eagle"}` |

`duration`, `queue_name`, and `account` are effectively required for a real job.

### Embedding module loads

There is no separate "module setup" step to worry about at the API layer — put
`module load ...` and environment setup directly in your command. When running a
script that needs the module system, invoke bash as a **login shell** (`-l`) so
`module` is initialized:

```json
{"executable": "/bin/bash", "arguments": ["-lc", "module load conda; conda activate base; python train.py"]}
```

### Queue limits (Polaris, reference)

| Queue | Nodes | Max wall time | Notes |
|-------|-------|---------------|-------|
| debug | 1–2 | 1 h (3600 s) | Typically 1 running job per user |
| debug-scaling | 1–10 | 1 h (3600 s) | |
| prod | 10–496 | 24 h (86400 s) | Routing queue |

Always confirm current limits in the ALCF Polaris docs; queue policy changes.

## Examples

### Submit a job

=== "cURL"

    ```bash
    access_token=$(python alcf_facility_api_globus_token.py get_access_token)
    resource_id="55c1c993-1124-47f9-b823-514ba3849a9a"   # Polaris

    curl -X POST "https://api.alcf.anl.gov/api/v1/compute/job/${resource_id}" \
         -H "Authorization: Bearer ${access_token}" \
         -H "Content-Type: application/json" \
         -d '{
               "executable": "/bin/bash",
               "arguments": ["-lc", "echo Start; sleep 10; echo End"],
               "name": "my_job",
               "stdout_path": "/home/<username>/logs",
               "stderr_path": "/home/<username>/logs",
               "resources": {"node_count": 1},
               "attributes": {
                   "duration": 300,
                   "queue_name": "debug",
                   "account": "<your-project>",
                   "custom_attributes": {"filesystems": "home:eagle"}
               }
             }'
    ```

=== "Python"

    ```python
    import requests
    from alcf_facility_api_globus_token import get_access_token

    BASE = "https://api.alcf.anl.gov/api/v1"
    POLARIS = "55c1c993-1124-47f9-b823-514ba3849a9a"
    headers = {"Authorization": f"Bearer {get_access_token()}",
               "Content-Type": "application/json"}

    body = {
        "executable": "/bin/bash",
        "arguments": ["-lc", "echo Start; sleep 10; echo End"],
        "name": "my_job",
        "stdout_path": "/home/<username>/logs",
        "stderr_path": "/home/<username>/logs",
        "resources": {"node_count": 1},
        "attributes": {
            "duration": 300,
            "queue_name": "debug",
            "account": "<your-project>",
            "custom_attributes": {"filesystems": "home:eagle"},
        },
    }
    r = requests.post(f"{BASE}/compute/job/{POLARIS}", json=body, headers=headers)
    print(r.status_code, r.json())
    ```

### List jobs

`POST /compute/status/{resource_id}` with query params `historical`, `limit`,
`offset`, `include_spec`. Returns a **list** of job objects; each has an `id`
(the PBS id, e.g. `3095452.polaris-pbs-01...`) and a nested
`status: {state, exit_code}`.

```python
r = requests.post(
    f"{BASE}/compute/status/{POLARIS}",
    params={"historical": "false", "limit": 10, "offset": 0},
    headers=headers,
)
for job in r.json():
    st = job.get("status") or {}
    print(job["id"], st.get("state"), st.get("exit_code"))
```

### Get one job

```python
r = requests.get(
    f"{BASE}/compute/status/{POLARIS}/{job_id}",
    params={"historical": "true"},
    headers=headers,
)
job = r.json()
print(job["id"], (job.get("status") or {}).get("state"))
```

### Cancel a job

Returns HTTP `204 No Content` on success.

```python
r = requests.delete(f"{BASE}/compute/cancel/{POLARIS}/{job_id}", headers=headers)
print("Canceled" if r.status_code == 204 else r.json())
```

## Common Pitfalls

- **`duration` is in SECONDS.** `attributes.duration = 60` is one minute; use
  `3600` for one hour.
- **Job state is nested.** Read `job["status"]["state"]` /
  `["exit_code"]`, not a top-level `state` field.
- **Forgetting the `-l` login shell** when a command needs `module`. Without it:
  `module: command not found`.
- **Wrong resource UUID.** Job ops need a *compute* resource UUID; filesystem
  ops need a *storage* one.
- **Cancel returns 204 with no body.** Don't call `.json()` on a successful
  cancel.
- **Do not use base64/GraphQL workarounds.** Those apply to the AmSC client, not
  the ALCF-direct REST API. Complex commands go straight into `arguments`.

## See Also

- `api-fundamentals.md` -- Auth, base URL, resource UUIDs, Cloudflare UA pitfall
- `output-retrieval.md` -- Reading job stdout/stderr after completion
- ALCF IRI API docs: <https://docs.alcf.anl.gov/services/iri-api/>
