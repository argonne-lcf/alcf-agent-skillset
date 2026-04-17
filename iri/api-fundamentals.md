---
title: "IRI API Fundamentals"
category: iri
systems:
  - all
tags:
  - iri
  - api
  - amsc-client
  - globus
  - authentication
description: >
  How to set up the amsc-client, authenticate via Globus, and navigate IRI API
  resources (facilities, compute resources, storage resources). Includes the
  filesystem API status table showing what works and what returns 501. Load
  before any IRI API interaction.
last_verified: "2026-04"
---

## Purpose

Foundation for all IRI API interactions. Covers authentication, client setup, and resource navigation. Load this skill before any IRI API interaction to understand the client setup, available resources, and filesystem API limitations.

## Prerequisites

- Python 3.8+
- `pip install amsc-client` (see install note below)
- Globus account linked to ALCF

## Key Facts

### Installing amsc-client

amsc-client is distributed via a private GitLab package registry. It requires `--extra-index-url` flags to install. Check the [amsc-client-tutorial repo](https://github.com/argonne-lcf/amsc-client-tutorial) for the current install command, as the index URL may change.

### Authentication

Auth uses Globus OAuth. The client constructor requires a Globus app ID, resource server ID, and scopes:

```python
from amsc_client import Client

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
```

- First run prompts for browser-based Globus authentication.
- Credentials are cached in `~/.amsc/credentials.json` for subsequent runs.

### Resource Handles

After authenticating, obtain handles to ALCF facilities and resources:

```python
alcf    = client.facility("alcf")
polaris = alcf.resource("Polaris")   # compute resource -- submit jobs
home    = alcf.resource("Home")      # storage resource -- read files at /home
eagle   = alcf.resource("Eagle")     # storage resource -- read files at /eagle
```

Available resource names:

| Resource | Type | Filesystem Mount |
|----------|------|------------------|
| Polaris | Compute | N/A (job submission only) |
| Home | Storage | `/home` |
| Eagle | Storage | `/eagle` |

### CRITICAL: Filesystem Operations and Resource Types

**Never call filesystem operations on compute resources.** `polaris.fs.*` operations return HTTP 400. Filesystem operations only work on storage resources (Home, Eagle).

```python
# WRONG -- returns HTTP 400
polaris.fs.ls("/home/username")

# CORRECT -- use storage resource
home.fs.ls("/home/username")
```

### Path Constraints

All filesystem paths must start with `/home/<user>` or `/eagle`. Paths not matching these prefixes are rejected.

### Filesystem API Status

| Operation | Status | Notes |
|-----------|--------|-------|
| ls | Working | On Home/Eagle only |
| head | Working | Read first N bytes |
| view | Working | Read full file content |
| chmod | Working | |
| chown | Working | |
| tail | 501 Not Implemented | |
| stat | 501 Not Implemented | |
| mkdir | 501 Not Implemented | Create dirs via job instead |
| cp/mv/rm | 501 Not Implemented | |
| download | 501 Not Implemented | |

## Examples

### Full Client Setup and Resource Navigation

```python
from amsc_client import Client

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

# Get facility and resource handles
alcf = client.facility("alcf")
polaris = alcf.resource("Polaris")
home = alcf.resource("Home")

# List files in home directory
task = home.fs.ls("/home/username")
task.wait(timeout=30)
print(task.result)
```

### Listing Available Facilities and Resources

```python
# List all facilities
facilities = client.facilities()
for f in facilities:
    print(f"Facility: {f.name}")

# List resources in a facility
alcf = client.facility("alcf")
resources = alcf.resources()
for r in resources:
    print(f"Resource: {r.name}")
```

## Common Pitfalls

- **`polaris.fs.ls()` returns HTTP 400.** Filesystem operations only work on storage resources. Use `home.fs.ls()` or `eagle.fs.ls()` instead.
- **`home.fs.tail()` returns 501.** Use `home.fs.view()` and slice the result: `content[-3000:]`.
- **Paths not starting with `/home/` or `/eagle/` are rejected.** Always use absolute paths rooted at these mounts.
- **First run requires interactive browser auth.** Cannot be automated in a headless environment without pre-cached credentials.

## See Also

- `job-submission.md` -- Submitting and monitoring PBS jobs through the IRI API
- `output-retrieval.md` -- Reading job stdout/stderr after completion
