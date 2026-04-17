---
title: "IRI Output Retrieval"
category: iri
systems:
  - all
tags:
  - iri
  - api
  - output
  - filesystem
description: >
  How to read job stdout/stderr through the IRI API after job completion.
  Covers output file routing, the fs.view() pattern, result parsing, and
  the tail workaround. Load after submitting a job via IRI.
last_verified: "2026-04"
---

## Purpose

Guide for reading job output (stdout/stderr) through the IRI API after job completion. Covers output file locations, the `fs.view()` pattern, result parsing across client versions, and workarounds for unimplemented operations.

## Prerequisites

- amsc-client installed and authenticated (see `api-fundamentals.md`)
- A completed job submitted via IRI (see `job-submission.md`)
- Home storage resource handle

## Key Facts

### Output File Routing

When a job is submitted with `directory` and `name` parameters, output lands at:

| Output | Path |
|--------|------|
| stdout | `{directory}/{name}.stdout` |
| stderr | `{directory}/{name}.stderr` |

For example, a job submitted with `directory="/home/user/project"` and `name="my-run"` produces:
- `/home/user/project/my-run.stdout`
- `/home/user/project/my-run.stderr`

### Reading Output via the Home Storage Resource

**Always use the Home storage resource** (`home.fs.view()`), never the compute resource (`polaris.fs.view()` returns HTTP 400).

```python
home = alcf.resource("Home")
task = home.fs.view(f"{WORK_DIR}/{job_name}.stdout")
task.wait(timeout=60)
content = task.result
```

### Filesystem Sync Delay

**Always `time.sleep(5)` before reading output** after job completion. The filesystem may not have synced the output files yet. Reading too soon produces empty or partial content.

### Result Parsing

The result format varies by client version -- it may be a dict or a raw string. Always handle both:

```python
task = home.fs.view(f"{WORK_DIR}/{fname}")
task.wait(timeout=60)
r = task.result
if isinstance(r, dict):
    content = r.get('output', r).get('content', '')
else:
    content = str(r)
```

### tail() Workaround

`home.fs.tail()` returns 501 (Not Implemented). To read the end of a file, read the full file with `view()` and slice:

```python
task = home.fs.view(f"{WORK_DIR}/{job_name}.stdout")
task.wait(timeout=60)
r = task.result
if isinstance(r, dict):
    content = r.get('output', r).get('content', '')
else:
    content = str(r)

# Get last 3000 characters (tail workaround)
tail_content = content[-3000:]
```

### Container Jobs: Check stderr First

For container MPI jobs, stderr is MORE informative than stdout. It contains module loads, Apptainer startup messages, Kokkos initialization output, and error details. Always check stderr when debugging container jobs.

## Examples

### Complete read_output() Function

```python
def read_output(home, work_dir, job_name, max_chars=10000):
    """Read stdout and stderr for a completed job.

    Args:
        home: Home storage resource handle
        work_dir: Job working directory
        job_name: Job name (from submit() name parameter)
        max_chars: Max characters to display per file (head+tail)

    Returns:
        dict with 'stdout' and 'stderr' content strings
    """
    import time
    time.sleep(5)
    results = {}
    for label, fname in [("stdout", f"{job_name}.stdout"),
                          ("stderr", f"{job_name}.stderr")]:
        try:
            task = home.fs.view(f"{work_dir}/{fname}")
            task.wait(timeout=60)
            r = task.result
            if isinstance(r, dict):
                content = r.get('output', r).get('content', '')
            else:
                content = str(r)
            results[label] = content
            print(f"\n-- {label.upper()} ({len(content)} chars) --")
            if len(content) > max_chars:
                half = max_chars // 2
                print(content[:half])
                print(f"\n... ({len(content) - max_chars} chars omitted) ...\n")
                print(content[-half:])
            else:
                print(content)
        except Exception as e:
            print(f"{label}: {type(e).__name__}: {e}")
    return results
```

### Usage with a Completed Job

```python
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
home = alcf.resource("Home")

# Read output from a completed job
results = read_output(home, "/home/username/my_project", "my-training-run")

# Access content programmatically
stdout_text = results.get("stdout", "")
stderr_text = results.get("stderr", "")
```

### Tail Workaround Function

```python
def tail_output(home, file_path, num_chars=3000):
    """Read the last num_chars of a file (workaround for tail() 501)."""
    task = home.fs.view(file_path)
    task.wait(timeout=60)
    r = task.result
    if isinstance(r, dict):
        content = r.get('output', r).get('content', '')
    else:
        content = str(r)
    return content[-num_chars:]

# Usage
last_lines = tail_output(home, "/home/username/my_project/my-run.stdout")
print(last_lines)
```

## Common Pitfalls

- **Reading too soon after job completion.** The filesystem may not have synced yet, producing empty or partial output. Always `time.sleep(5)` before reading.
- **Using `polaris.fs.view()` instead of `home.fs.view()`.** Compute resources do not support filesystem operations. Returns HTTP 400.
- **Not handling both dict and string result formats.** Different client versions return different types. Always check `isinstance(r, dict)` before accessing keys.
- **Using `home.fs.tail()`.** Returns 501 Not Implemented. Read the full file with `view()` and slice the result.
- **Only checking stdout for container jobs.** For container MPI jobs, stderr contains module loads, Apptainer messages, and most error details. Always read both.

## See Also

- `api-fundamentals.md` -- Client setup, authentication, and filesystem API status
- `job-submission.md` -- Submitting and monitoring PBS jobs through the IRI API
