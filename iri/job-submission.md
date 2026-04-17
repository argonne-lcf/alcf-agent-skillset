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
  - base64
description: >
  How to submit and monitor PBS jobs through the IRI API using amsc-client.
  Covers the base64 script transfer workaround, queue limits, and the two-step
  submission pattern. Load when submitting jobs via IRI.
last_verified: "2026-04"
---

## Purpose

Guide for submitting and monitoring PBS jobs through the IRI API using amsc-client. Covers the submit() parameters, queue limits, and the critical base64 two-step workaround for complex scripts.

## Prerequisites

- amsc-client installed and authenticated (see `api-fundamentals.md`)
- ALCF allocation with a valid project account
- Polaris compute resource handle

## Key Facts

### submit() Parameters

`polaris.submit()` accepts the following parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| executable | str | Path to executable (e.g., `/bin/bash`) |
| arguments | list[str] | Arguments to the executable |
| directory | str | Working directory on the compute node |
| name | str | Job name (used in output filenames) |
| queue | str | PBS queue name |
| account | str | Project allocation account |
| duration | int | Wall time in **SECONDS** (not minutes) |
| nodes | int | Number of nodes |
| filesystems | str | Filesystem mounts needed (e.g., `"home:eagle"`) |

### Queue Limits

| Queue | Nodes | Max Duration | Notes |
|-------|-------|-------------|-------|
| debug | 1-2 | 1 hour (3600s) | Max 1 job at a time per user |
| debug-scaling | 1-10 | 1 hour (3600s) | |
| prod | 10-496 | 24 hours (86400s) | |

### CRITICAL: pre_launch Is Not Implemented

The `pre_launch` parameter returns 501 (Not Implemented). Do NOT use it. Embed all `module load` commands directly in the job script.

### The Base64 Script Transfer Pattern

Complex bash arguments with special characters (colons, dollar signs, quotes, semicolons) break the GraphQL parser, returning HTTP 400. The workaround is a two-step base64 script transfer pattern.

**Why base64:** The base64-encoded output contains only alphanumeric characters, `+`, `/`, and `=`, which are all safe for the GraphQL parser.

**Step 1: Write the script to the filesystem via a decode job**

```python
import base64
import time

SCRIPT_CONTENT = """#!/bin/bash
module load conda
conda activate base
python my_script.py --flag=value
"""

WORK_DIR = "/home/username/my_project"

b64 = base64.b64encode(SCRIPT_CONTENT.encode()).decode()
decode_cmd = f"echo {b64} | base64 -d > {WORK_DIR}/run.sh && chmod +x {WORK_DIR}/run.sh && echo OK"

write_job = polaris.submit(
    executable="/bin/bash",
    arguments=["-c", decode_cmd],
    directory=WORK_DIR,
    name="write-script",
    queue="debug",
    account="my_project",
    duration=300,       # 5 minutes in seconds
    nodes=1,
    filesystems="home",
)
write_job.wait(timeout=600, poll_interval=10)
time.sleep(3)  # filesystem sync delay
```

**Step 2: Execute the script with a login shell**

```python
run_job = polaris.submit(
    executable="/bin/bash",
    arguments=["-l", f"{WORK_DIR}/run.sh"],
    directory=WORK_DIR,
    name="my-run",
    queue="debug",
    account="my_project",
    duration=3600,      # 1 hour in seconds
    nodes=1,
    filesystems="home:eagle",
)
run_job.wait(timeout=1800, poll_interval=15)
print(f"Job state: {run_job.state}, exit code: {run_job.exit_code}")
```

**Always use `-l` (login shell flag)** when executing scripts so that `module` commands work. Without it, the module system is not initialized and `module: command not found` errors occur.

**Always add `time.sleep(3)`** after the write job completes to avoid filesystem sync race conditions where the script file is not yet visible to the next job.

### Job Monitoring

```python
# Wait for job to complete (blocking)
job.wait(timeout=1800, poll_interval=15)

# Check job state
print(job.state)      # "completed", "failed", "active", "queued"
print(job.exit_code)  # 0 on success
```

### Job Listing

```python
# List recent jobs
jobs = polaris.jobs(limit=20)
for j in jobs:
    print(f"{j.id}: {j.name} - {j.state}")

# Get a specific job by ID
job = polaris.job(job_id)
print(f"State: {job.state}, Exit: {job.exit_code}")
```

## Examples

### Complete Two-Step Job Submission

```python
import base64
import time
from amsc_client import Client

# -- Client setup (see api-fundamentals.md) --
GLOBUS_APP_ID = 'e4f48665-38b5-4833-a89e-849c71f5b3e3'
RESOURCE_SERVER = '8b84fc2d-49e9-49ea-b54d-b3a29a70cf31'

client = Client(
    base_url='https://api.american-science-cloud.org/api/current',
    auth_method="globus",
    globus_client_id=GLOBUS_APP_ID,
    requested_scopes=(
        f'openid profile email '
        f'https://auth.globus.org/scopes/{GLOBUS_APP_ID}/amsc_test'
    ),
    resource_server=RESOURCE_SERVER,
    use_id_token=True,
)

alcf = client.facility("alcf")
polaris = alcf.resource("Polaris")

# -- Job parameters --
WORK_DIR = "/home/username/my_project"
ACCOUNT = "my_project"

SCRIPT = """#!/bin/bash
module load conda
conda activate base
echo "Running on $(hostname)"
python train.py --epochs=10
echo "Done"
"""

# -- Step 1: Write script via base64 --
b64 = base64.b64encode(SCRIPT.encode()).decode()
decode_cmd = f"echo {b64} | base64 -d > {WORK_DIR}/run.sh && chmod +x {WORK_DIR}/run.sh && echo OK"

write_job = polaris.submit(
    executable="/bin/bash",
    arguments=["-c", decode_cmd],
    directory=WORK_DIR,
    name="write-script",
    queue="debug",
    account=ACCOUNT,
    duration=300,
    nodes=1,
    filesystems="home",
)
print(f"Write job submitted: {write_job.id}")
write_job.wait(timeout=600, poll_interval=10)
time.sleep(3)

# -- Step 2: Execute the script --
run_job = polaris.submit(
    executable="/bin/bash",
    arguments=["-l", f"{WORK_DIR}/run.sh"],
    directory=WORK_DIR,
    name="my-training-run",
    queue="debug",
    account=ACCOUNT,
    duration=3600,
    nodes=1,
    filesystems="home:eagle",
)
print(f"Run job submitted: {run_job.id}")
run_job.wait(timeout=1800, poll_interval=15)
print(f"State: {run_job.state}, Exit code: {run_job.exit_code}")
```

### Listing Recent Jobs

```python
jobs = polaris.jobs(limit=20)
for j in jobs:
    print(f"  {j.id}: {j.name:30s} state={j.state:10s} exit={j.exit_code}")
```

## Common Pitfalls

- **`duration` is in SECONDS, not minutes.** Passing `60` gives you 60 seconds, not 60 minutes. For 1 hour, use `3600`.
- **Debug queue: max 1 job at a time per user.** Wait for the previous job to complete plus a 30-second buffer before submitting the next one.
- **Forgetting the `-l` flag when executing scripts.** Without the login shell flag, the module system is not initialized: `module: command not found`.
- **Writing complex bash directly in `arguments`.** Special characters break the GraphQL parser with HTTP 400. Always use the base64 two-step pattern.
- **Not sleeping after the write job.** The filesystem may not have synced the script file yet. Always `time.sleep(3)` between step 1 and step 2.
- **Using `pre_launch` parameter.** Returns 501 Not Implemented. Embed module loads in the script itself.

## See Also

- `api-fundamentals.md` -- Client setup, authentication, and resource handles
- `output-retrieval.md` -- Reading job stdout/stderr after completion
- `../containers/polaris-container-run.md` -- Running containers on Polaris compute nodes
