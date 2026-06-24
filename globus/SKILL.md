---
title: "ALCF Facility Multiuser Globus Compute Endpoints"
name: alcf-globus-multiuser-endpoints
category: jobs
systems: [polaris, crux]
tags: [globus-compute, multiuser-endpoint, polaris, crux, pbs, user-endpoint-config]
description: >
  Reference for the facility-supported multiuser Globus Compute endpoints on
  Polaris and Crux. Covers endpoint UUIDs, the user_endpoint_config schema
  (what keys are accepted and validated), the Jinja config template
  (defaults, hardcoded paths, launcher branching), auth, and how to drive the
  endpoints from a Python SDK client. Load when configuring or invoking a
  facility multiuser endpoint, or when overriding queue / launcher / nodes /
  walltime / worker_init from the client side.
last_verified: "2026-06"
alcf_docs_url: "https://globus-compute.readthedocs.io/en/latest/endpoints/multi_user.html"
---

# alcf-globus-multiuser-endpoints — Facility multiuser endpoints on Polaris and Crux

ALCF runs facility-supported multiuser Globus Compute endpoints on Polaris
and Crux. They accept tasks from any authorized user and submit PBS jobs on
the user's behalf using a fixed Jinja config template. Clients control the
PBS submission by passing a `user_endpoint_config` dict — that dict is
validated against a JSON Schema, then rendered through the template to
produce the per-user endpoint config.

This skill documents what the endpoint accepts, what it does with each
field, and how to invoke it from a Python client.

## Purpose

When you submit work through a facility multiuser endpoint, you do not run
`globus-compute-endpoint configure` locally — the endpoint already exists
on the cluster. Instead, every submission carries a `user_endpoint_config`
that the endpoint validates and substitutes into its Jinja template. To
drive these endpoints well you need to know:

- Which UUIDs to target.
- Which keys the schema accepts (and which are required).
- What the template's defaults are, and which fields are hardcoded.
- How to override behavior (longer walltime, more nodes, MPI launcher,
  custom `worker_init`) without breaking the schema.

## Prerequisites

- A Globus Auth identity linked to an ALCF account with an active project
  allocation on the target system.
- `globus-compute-sdk` installed locally (Python ≥3.10 recommended; mismatch
  with worker Python triggers a warning, see Common Pitfalls).
- First call in a fresh environment opens an interactive browser login to
  refresh Globus Auth tokens cached under `~/.globus_compute/`.
- Familiarity with `alcf-remote-bash` if you just want to run bash on the
  endpoint — it wraps the SDK call.

## Key Facts

- **Endpoint UUIDs (as of 2026-06):**
  - Polaris: `9a947ba5-f537-4681-acf3-cc66485aadec`
  - Crux:    `d01d0c83-e570-4977-9170-1b8f2316e7c6`
- **Auth:** Globus Auth tokens in `~/.globus_compute/`. No `alcf_access_token`
  or IRI involvement.
- **Required `user_endpoint_config` keys:** `queue`, `account`. Everything
  else is optional and falls back to template defaults.
- **`additionalProperties: true`** on the schema — unknown keys (e.g.
  `max_retries_on_system_failure`, `walltime`, `nodes_per_block`) pass
  validation and reach the template; the template only substitutes the
  Jinja vars it knows about, so unrecognized keys are silently ignored.
- **Worker venv is hardcoded** in the template's default `worker_init`
  (`export PATH="$PATH":/opt/globus-compute-agent/venv-py313/bin/`). The
  worker Python is 3.13. To change the worker env, pass your own
  `worker_init` string.
- **The template hardcodes `system=polaris`** as the default
  `select_options`. On Crux the multiuser endpoint runs its own template
  with a Crux-appropriate default; override `select_options` if you need
  a non-default select string on either system.
- **Launcher defaults to `SimpleLauncher`.** Set `launcher_type` to
  `MpiExecLauncher` for multi-rank work; only then do `bind_cmd` and
  `overrides` get substituted.
- **One submission = one PBS job under the hood.** Every `gce.submit()` call
  consumes a queue slot. Don't loop these for polling.

## The schema

The Polaris multiuser endpoint's `user_endpoint_config_schema.json`:

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

`additionalProperties: true` is the important part. Any extra key you pass
(e.g. `walltime`, `nodes_per_block`, `max_blocks`, `scheduler_options`,
`max_retries_on_system_failure`, `max_workers_per_node`, `max_idletime`)
passes the validator and is fed to the Jinja template — the template
substitutes the ones it has variables for and ignores the rest.

## The Jinja template

The Polaris template (`user_config_template.yaml.j2`) the endpoint renders
per submission:

```yaml
{% set launcher_type = launcher_type | default("SimpleLauncher") -%}
endpoint_setup: {{ endpoint_setup | default() }}
idle_heartbeats_soft: 10
idle_heartbeats_hard: 5760
engine:
  type: GlobusComputeEngine
  max_retries_on_system_failure: {{ max_retries_on_system_failure | default(0) }}
  max_workers_per_node: {{ max_workers_per_node | default(100) }}
  job_status_kwargs:
    max_idletime: {{ max_idletime | default(240) }}
  address:
    type: address_by_interface
    ifname: hsn0
  provider:
    type: PBSProProvider
    worker_init: {{ worker_init | default("\"export TMPDIR=/tmp; export PATH=\\\"$PATH\\\":/opt/globus-compute-agent/venv-py313/bin/\"") }}
    launcher:
      type: {{ launcher_type }}
{% if launcher_type == '"MpiExecLauncher"' %}
      bind_cmd: {{ bind_cmd | default("--cpu-bind") }}
      overrides: {{ overrides | default("\"--depth=64 --ppn 1\"") }}
{% endif %}
    queue: {{ queue }}
    select_options: {{ select_options | default("system=polaris") }}
    account: {{ account }}
    scheduler_options: {{ scheduler_options | default("\"#PBS -l filesystems=home\"") }}
    init_blocks: {{ init_blocks | default(0) }}
    max_blocks: {{ max_blocks | default(1) }}
    min_blocks: {{ min_blocks | default(0) }}
    nodes_per_block: {{ nodes_per_block | default(1) }}
    walltime: {{ walltime | default("1:00:00") }}
```

What this means in practice:

- **`worker_init` default** activates the system globus-compute agent venv on
  `PATH` and sets `TMPDIR=/tmp`. Override this string to bring in modules,
  a project conda env, or extra LD library paths. The override REPLACES
  the default — include the agent venv PATH export yourself if you still
  want it.
- **`launcher_type == MpiExecLauncher`** is the *only* path that surfaces
  `bind_cmd` and `overrides`. Passing them with `SimpleLauncher` is silently
  ignored.
- **`scheduler_options` default** only requests the `home` filesystem. For
  jobs that read or write under `/eagle` or `/grand`, override it:
  `"#PBS -l filesystems=home:eagle"`.
- **`select_options` default is `system=polaris`** on the Polaris template.
  Override on Crux if needed (the Crux template uses a Crux-appropriate
  default).
- **`init_blocks=0`, `max_blocks=1`, `min_blocks=0`** means a block is
  provisioned on demand — your first submit triggers a PBS job; subsequent
  submits within `max_idletime` (default 240s) reuse it.
- **`max_workers_per_node=100`** is high enough that single-task submissions
  never queue waiting for a slot.

## Auth

Globus Compute uses its own auth. The first SDK call in a session opens a
browser login (or prints a device-code URL in headless contexts) and caches
tokens under `~/.globus_compute/`. Tokens auto-refresh; on expiry the next
call re-prompts.

If you hit an auth error in a non-interactive environment (CI, agent
sandbox without a browser), run any submission interactively once on the
same machine to seed the cache.

## Driving the endpoint from Python

Minimal pattern. Pass your function, `user_endpoint_config`, and submit:

```python
from globus_compute_sdk import Executor
from globus_compute_sdk.serialize import ComputeSerializer, CombinedCode

POLARIS = "9a947ba5-f537-4681-acf3-cc66485aadec"
CRUX    = "d01d0c83-e570-4977-9170-1b8f2316e7c6"

def hello():
    import socket
    return f"hello from {socket.gethostname()}"

config = {
    "account": "datascience",
    "queue":   "debug",
}

serializer = ComputeSerializer(strategy_code=CombinedCode())
with Executor(endpoint_id=POLARIS,
              user_endpoint_config=config,
              serializer=serializer) as gce:
    future = gce.submit(hello)
    print(future.result(timeout=300))
```

To customize the PBS job, add the extra keys to `config`:

```python
config = {
    "account":        "datascience",
    "queue":          "debug",
    "walltime":       "0:30:00",
    "nodes_per_block": 2,
    "scheduler_options": '"#PBS -l filesystems=home:eagle"',
    "worker_init": (
        'export TMPDIR=/tmp; '
        'export PATH="$PATH":/opt/globus-compute-agent/venv-py313/bin/; '
        'module use /soft/modulefiles && module load conda && '
        'source /eagle/<project>/<user>/setup_polaris.sh'
    ),
    "launcher_type":  "MpiExecLauncher",
    "overrides":      '"--depth=64 --ppn 1"',
}
```

Note the quoting on `scheduler_options` and `overrides`: the template
substitutes the value verbatim, and YAML needs the leading `#PBS -l ...` to
stay a string, not a comment. Wrap it in `"..."` inside the Python string.

For bash one-shots use `alcf-remote-bash` instead — it ships the same
pattern wrapped behind a CLI.

## Examples

### Hello world on Polaris (Python SDK)

```bash
python - <<'PY'
from globus_compute_sdk import Executor
from globus_compute_sdk.serialize import ComputeSerializer, CombinedCode

def hello():
    import socket, time
    time.sleep(60)
    return f"hello from {socket.gethostname()}"

with Executor(
    endpoint_id="9a947ba5-f537-4681-acf3-cc66485aadec",
    user_endpoint_config={"account": "datascience", "queue": "debug"},
    serializer=ComputeSerializer(strategy_code=CombinedCode()),
) as gce:
    print(gce.submit(hello).result(timeout=180))
PY
```

### Multi-node MPI launcher

```python
config = {
    "account":          "datascience",
    "queue":            "debug",
    "walltime":         "0:30:00",
    "nodes_per_block":  4,
    "launcher_type":    "MpiExecLauncher",
    "overrides":        '"--depth=64 --ppn 1"',
    "scheduler_options": '"#PBS -l filesystems=home:eagle"',
}
```

Pair this with a function that calls `mpiexec` inside its body, or that
uses Parsl-style MPI tasks.

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

## Common Pitfalls

- **If you see `additional properties are not allowed` errors:** the
  endpoint administrator has tightened the schema; check the schema's
  `additionalProperties` field. The current ALCF facility endpoints have it
  set to `true`, so this typically means you misread an error — re-read it.
- **If `worker_init` overrides break the worker:** you replaced the default
  PATH export; the worker process can't find its own venv. Always include
  `export PATH="$PATH":/opt/globus-compute-agent/venv-py313/bin/` (or the
  current default) in any override.
- **If `bind_cmd` / `overrides` seem ignored:** the template only
  substitutes them under `launcher_type == "MpiExecLauncher"`. Confirm
  `launcher_type` is set; otherwise they're dead.
- **If you see `RuntimeError: can't create new thread at interpreter
  shutdown`:** cosmetic SDK atexit trace; the result has already been
  returned. Ignore.
- **If you see `Environment differences detected ... SDK: Python X / Workers:
  Python Y`:** SDK and endpoint worker Python versions differ. Usually
  harmless; if you hit a deserialization error, match the local Python to
  the worker (currently 3.13) or simplify the payload to avoid version-
  specific pickle behavior.
- **If your first call hangs:** it's blocking on browser auth. Run once
  interactively to seed `~/.globus_compute/`, then retry headless.
- **If `walltime` overrides are ignored:** confirm you passed it as a
  string in `HH:MM:SS` format. Numbers and `30m`-style shorthand are not
  parsed by the template.
- **If your job sits in queue past `future.result(timeout=...)`:** the
  local future raises `TimeoutError` even though PBS still has the job.
  The submitted task continues on the endpoint — increase the local timeout
  or use `future.task_id` to reconnect.

## See Also

- `../remote-bash/SKILL.md` — bash-command wrapper around these endpoints
- `../iri/job-submission.md` — alternative when you want IRI's submit/poll
  semantics or non-Globus auth
- `../systems/polaris/overview.md` — Polaris queue and filesystem reference
- `../systems/crux/overview.md` — Crux queue and filesystem reference
- https://globus-compute.readthedocs.io/en/latest/endpoints/multi_user.html
- https://globus-compute.readthedocs.io/en/latest/sdk/executor_user_guide.html
