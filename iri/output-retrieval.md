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
  How to read job stdout/stderr through the ALCF IRI API after a job completes,
  using the async filesystem head/view endpoints and task polling. Covers the
  verified result nesting, the tail (501) workaround, and container-job
  debugging. Load after submitting a job via IRI.
last_verified: "2026-07"
---

## Purpose

Guide for reading job output (stdout/stderr) through the ALCF IRI API after a job
completes. Covers where output lands, reading it via the async filesystem
endpoints, parsing the result, and workarounds for unimplemented operations.

> **ALCF-direct API** (`https://api.alcf.anl.gov/api/v1`). Filesystem reads are
> **asynchronous**: each call returns a task id you poll via `GET /task/{id}`.
> See `api-fundamentals.md`. This is different from the AmSC (`amsc-client`)
> `home.fs.view()` path.

## Prerequisites

- A valid IRI access token (see `api-fundamentals.md`)
- A completed job submitted via IRI (see `job-submission.md`)
- The **storage** resource UUID for the filesystem holding the output
  (Home `6115bd2c-957a-4543-abff-5fae52992ff2`, Eagle `1c3ad9d4-2e91-42bc-becb-72b1fde1235c`)

## Key Facts

### Output file routing

Where stdout/stderr land depends on the `stdout_path` / `stderr_path` you gave
at submit time (and the scheduler's naming). If you set them to a directory,
PBS writes `<name>.o<jobid>` / `<name>.e<jobid>` style files there; if you set
explicit file paths, output goes to those files. Record the exact paths you
submitted with so you know what to read back.

### Read via a STORAGE resource, with the async task flow

Filesystem reads run against a **storage** resource (Home/Eagle), never a
compute resource. Every read is a two-step async flow:

1. Call `GET /filesystem/head/{storage_id}` or `GET /filesystem/view/{storage_id}`
   → returns a **task id**.
2. Poll `GET /task/{task_id}` until `status` is `completed` (or `failed`/`error`),
   then read the content.

- **`head`** returns the first N **lines** (`lines` param);
  content nests at `result.output.content` with `content_type: "lines"`.
- **`view`** returns `size` **bytes** starting at `offset`;
  content nests at `result.output.content` with `content_type: "bytes"`.

### Verified result nesting

For a completed `head`/`view` task, the text is at:

```
task["result"]["output"]["content"]
```

Guard defensively, since intermediate levels can be absent on error:

```python
def extract_content(task):
    res = task.get("result") or {}
    out = res.get("output")
    if isinstance(out, dict):
        return out.get("content", "")
    # some ops return a bare string or list under result
    return out if isinstance(out, str) else res.get("content", "")
```

### `tail` is 501 — slice a `view` instead

`GET /filesystem/tail/{rid}` returns **501 Not Implemented**. To read the end of
a file, `view` it (optionally with a large `offset`) and slice the content:
`content[-3000:]`.

### Container jobs: check stderr first

For container / MPI jobs, **stderr** is usually more informative than stdout —
it carries module loads, Apptainer startup messages, and error details. Read
both, but look at stderr first when debugging.

## Examples

### Read the first lines of a file (head)

```python
import time
import requests
from alcf_facility_api_globus_token import get_access_token

BASE = "https://api.alcf.anl.gov/api/v1"
HOME = "6115bd2c-957a-4543-abff-5fae52992ff2"
headers = {"Authorization": f"Bearer {get_access_token()}"}

def poll(task_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        t = requests.get(f"{BASE}/task/{task_id}", headers=headers).json()
        if t.get("status") in ("completed", "failed", "error"):
            return t
        time.sleep(1)
    raise TimeoutError(task_id)

def extract_content(task):
    res = task.get("result") or {}
    out = res.get("output")
    if isinstance(out, dict):
        return out.get("content", "")
    return out if isinstance(out, str) else res.get("content", "")

# head: first 40 lines
r = requests.get(f"{BASE}/filesystem/head/{HOME}",
                 params={"path": "/home/<username>/logs/my_job.o12345", "lines": 40},
                 headers=headers)
r.raise_for_status()
task = poll(r.json()["id"])
print(extract_content(task))
```

### Read a byte range (view) and tail-by-slice

```python
# view: 4096 bytes from the start
r = requests.get(f"{BASE}/filesystem/view/{HOME}",
                 params={"path": "/home/<username>/logs/my_job.o12345",
                         "size": 4096, "offset": 0},
                 headers=headers)
task = poll(r.json()["id"])
content = extract_content(task)

# tail workaround: last 3000 chars
print(content[-3000:])
```

### Read stdout and stderr for a completed job

```python
def read_output(storage_id, stdout_path, stderr_path, lines=200):
    out = {}
    for label, path in (("stdout", stdout_path), ("stderr", stderr_path)):
        try:
            r = requests.get(f"{BASE}/filesystem/head/{storage_id}",
                             params={"path": path, "lines": lines}, headers=headers)
            r.raise_for_status()
            out[label] = extract_content(poll(r.json()["id"]))
        except Exception as e:
            out[label] = f"<{type(e).__name__}: {e}>"
    return out
```

## Common Pitfalls

- **Skipping the async poll.** `head`/`view` return a task id; you must poll
  `GET /task/{task_id}` for the content.
- **Reading the wrong nesting.** Content is at `result.output.content`, not at
  `result` directly. Use a defensive extractor.
- **Using a compute resource UUID for a read.** Filesystem ops need a storage
  UUID (Home/Eagle).
- **Calling `tail`.** It returns 501 — `view` and slice instead.
- **Reading immediately after job completion.** The filesystem may not have
  flushed yet; if content looks empty/partial, retry after a short delay.
- **Only checking stdout for container jobs.** stderr holds the module/Apptainer
  detail — read it first when debugging.

## See Also

- `api-fundamentals.md` -- Auth, resource UUIDs, async task model, FS status table
- `job-submission.md` -- Submitting and monitoring PBS jobs through the IRI API
- ALCF IRI API docs: <https://docs.alcf.anl.gov/services/iri-api/>
