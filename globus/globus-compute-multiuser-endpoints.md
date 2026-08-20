---
title: "ALCF Facility Multiuser Globus Compute Endpoints"
name: alcf-globus-compute-multiuser-endpoints
category: jobs
systems: [polaris, crux]
tags: [globus-compute, multiuser-endpoint, polaris, crux, pbs, user-endpoint-config]
description: >
  Reference for the facility-supported multiuser Globus Compute endpoints on
  Polaris and Crux. Covers endpoint UUIDs, the user_endpoint_config schema,
  the Jinja config template, auth, and how to drive the endpoints from a
  Python SDK client for single-task and small fan-out workloads. Load when
  configuring or invoking a facility multiuser endpoint. For multi-node
  fan-out (place=scatter), block lifecycle, and GPU caveats, also load
  alcf-globus-compute-multi-node.
last_verified: "2026-06"
globus_docs_url: "https://globus-compute.readthedocs.io/en/latest/endpoints/multi_user.html"
---

# alcf-globus-compute-multiuser-endpoints — Facility multiuser endpoints on Polaris and Crux

ALCF runs facility-supported multiuser Globus Compute endpoints on Polaris
and Crux. They accept tasks from any authorized user and submit PBS jobs on
the user's behalf using a fixed Jinja config template. Clients control the
PBS submission by passing a `user_endpoint_config` dict — that dict is
validated against a JSON Schema, then rendered through the template to
produce the per-user endpoint config.

## Purpose

When you submit work through a facility multiuser endpoint, you do not run
`globus-compute-endpoint configure` locally — the endpoint already exists
on the cluster. Every submission carries a `user_endpoint_config` that the
endpoint validates and substitutes into its Jinja template. To drive these
endpoints well you need to know which UUIDs to target, which keys the
schema accepts, what the template defaults are, and how to override
behavior without breaking the schema.

For multi-node fan-out (`place=scatter`), the block/job/task lifecycle,
and per-worker GPU binding, see `alcf-globus-compute-multi-node`.

## Prerequisites

- A Globus Auth identity linked to an ALCF account with an active project
  allocation on the target system.
- `globus-compute-sdk` installed locally.
- First call in a fresh environment opens an interactive browser login to
  refresh Globus Auth tokens cached under `~/.globus_compute/`.

## Key Facts

- **Endpoint UUIDs (as of 2026-06):**
  - Polaris: `9a947ba5-f537-4681-acf3-cc66485aadec`
  - Crux:    `d01d0c83-e570-4977-9170-1b8f2316e7c6`
- **Auth:** Globus Auth tokens in `~/.globus_compute/`. No IRI involvement.
- **Required `user_endpoint_config` keys:** `queue`, `account`. Everything
  else is optional and falls back to template defaults.
- **`additionalProperties: true`** on the schema — unknown keys (e.g.
  `walltime`, `nodes_per_block`, `scheduler_options`, `max_blocks`) pass
  validation and reach the template; the template only substitutes the
  Jinja vars it knows about, so unrecognized keys are silently ignored.
- **Worker venv is hardcoded** in the template's default `worker_init`
  (`export PATH="$PATH":/opt/globus-compute-agent/venv-py313/bin/`). Worker
  Python is 3.13. To change the worker env, pass your own `worker_init`.
- **Launcher defaults to `SimpleLauncher`.** Set `launcher_type` to
  `MpiExecLauncher` to spawn worker pools per node — needed for multi-node
  fan-out (see `alcf-globus-compute-multi-node`).

## The schema

```json
{
  "type": "object",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "required": ["queue", "account"],
  "properties": {
    "queue":          {"type": "string", "minLength": 1},
    "account":        {"type": "string", "minLength": 1},
    "bind_cmd":       {"type": "string"},
    "overrides":      {"type": "string"},
    "worker_init":    {"type": "string"},
    "launcher_type":  {"enum": ["SimpleLauncher", "MpiExecLauncher"],
                       "type": "string", "default": "SimpleLauncher"},
    "endpoint_setup": {"type": "string"},
    "select_options": {"type": "string"}
  },
  "additionalProperties": true
}
```

`additionalProperties: true` is the important part. Any extra key
(`walltime`, `nodes_per_block`, `max_blocks`, `scheduler_options`,
`max_workers_per_node`, `max_idletime`, etc.) passes validation and feeds
the template — the template substitutes what it knows about and ignores
the rest.

## Template defaults (cheat sheet)

The endpoint's Jinja template fills these defaults when a key is absent:

| key | default | notes |
|---|---|---|
| `walltime` | `1:00:00` | string `HH:MM:SS` |
| `nodes_per_block` | `1` | PBS `select=N:ncpus=1:system=<machine>` |
| `max_workers_per_node` | `100` | concurrency per node |
| `max_idletime` | `240` | seconds before idle block tears down |
| `init_blocks` / `min_blocks` / `max_blocks` | `0` / `0` / `1` | provision on demand, at most one PBS job |
| `launcher_type` | `SimpleLauncher` | swap to `MpiExecLauncher` for multi-node |
| `worker_init` | activates `/opt/globus-compute-agent/venv-py313` on PATH | full override REPLACES default |
| `scheduler_options` | `#PBS -l filesystems=home` | full override REPLACES default — re-include `filesystems=` |
| `select_options` | `system=polaris` (Polaris) / `system=crux` (Crux) | only `system=` differs between machines |

## Auth

The first SDK call in a session opens a browser login (or device-code URL
in headless contexts) and caches tokens under `~/.globus_compute/`. Tokens
auto-refresh; on expiry the next call re-prompts.

If you hit an auth error in a non-interactive environment (CI, agent
sandbox without a browser), run any submission interactively once on the
same machine to seed the cache.

## Examples

### Hello world (Polaris or Crux — swap the UUID)

```python
from globus_compute_sdk import Executor
from globus_compute_sdk.serialize import ComputeSerializer, CombinedCode

POLARIS = "9a947ba5-f537-4681-acf3-cc66485aadec"
CRUX    = "d01d0c83-e570-4977-9170-1b8f2316e7c6"

def hello():
    import socket
    return f"hello from {socket.gethostname()}"

config = {"account": "datascience", "queue": "debug"}

with Executor(
    endpoint_id=POLARIS,
    user_endpoint_config=config,
    serializer=ComputeSerializer(strategy_code=CombinedCode()),
) as gce:
    print(gce.submit(hello).result(timeout=900))
```

Use a generous `result(timeout=...)` (≥600s) — the first call after an
idle endpoint pays PBS queue wait.

### Override `worker_init` to bring in a project env

```python
config = {
    "account": "datascience",
    "queue":   "debug",
    "worker_init": (
        'export TMPDIR=/tmp; '
        'export PATH="$PATH":/opt/globus-compute-agent/venv-py313/bin/; '
        'module use /soft/modulefiles && module load conda && '
        'conda activate /eagle/datascience/<you>/envs/myenv'
    ),
}
```

The override REPLACES the default `worker_init`. Always re-include the
agent venv PATH export or the worker won't find its own Python.

## Common Pitfalls

- **`worker_init` override breaks the worker:** you dropped the agent venv
  PATH export. Always include
  `export PATH="$PATH":/opt/globus-compute-agent/venv-py313/bin/`.
- **`scheduler_options` override gets rejected by qsub** with
  "`Resource: filesystems is required to be set`": you dropped the default
  `#PBS -l filesystems=home`. Re-include `filesystems=...` in any override.
- **`bind_cmd` / `overrides` seem ignored:** the template only substitutes
  them when `launcher_type == "MpiExecLauncher"`. With `SimpleLauncher`
  they're dead.
- **`RuntimeError: can't create new thread at interpreter shutdown`:**
  cosmetic SDK atexit trace after the result returned. Ignore.
- **`Environment differences detected ... SDK: Python X / Workers: Python Y`:**
  SDK and worker Python differ (workers currently 3.13). Usually harmless;
  if you hit a deserialization error, match local Python to the worker.
- **First call hangs:** blocking on browser auth. Run once interactively
  to seed `~/.globus_compute/`, then retry headless.
- **`walltime` ignored:** must be string `HH:MM:SS`. Numbers and `30m`-style
  shorthand are not parsed.
- **`gce.submit()` future times out while PBS still has the job:** the
  local future raises `TimeoutError` but the task continues on the
  endpoint. Increase `result(timeout=...)` or use `future.task_id` to
  reconnect.

## See Also

- `alcf-globus-compute-multi-node` — distributing workers across nodes
  (`place=scatter`), block/job/task lifecycle, GPU binding caveats
- `../remote-bash/SKILL.md` — bash-command wrapper around these endpoints
- `../iri/job-submission.md` — alternative when you want IRI's submit/poll
  semantics or non-Globus auth
- `../systems/polaris/overview.md` / `../systems/crux/overview.md`
- https://globus-compute.readthedocs.io/en/latest/endpoints/multi_user.html
- https://globus-compute.readthedocs.io/en/latest/sdk/executor_user_guide.html
