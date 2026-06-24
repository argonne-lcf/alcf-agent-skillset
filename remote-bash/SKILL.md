---
title: "Run Bash on ALCF Endpoints via Globus Compute"
name: alcf-remote-bash
category: jobs
systems: [polaris, crux]
tags: [globus-compute, remote-bash, polaris, crux, interactive, env-probe]
description: >
  Run a bash command on an ALCF compute endpoint (polaris / crux) via Globus
  Compute, using the wrapper script `remote-bash/remote_bash.py` in the repo.
  Use when the user wants to execute something on an ALCF system without going
  through the IRI API — typically for short interactive-style runs, env probes,
  or driving an existing analysis script. NOT a replacement for alcf-iri-job:
  this submits via Globus Compute, which queues a PBS job under the hood and
  waits synchronously for stdout/stderr.
last_verified: "2026-06"
---

# alcf-remote-bash — Run bash on an ALCF endpoint via Globus Compute

`remote-bash/remote_bash.py` is a small typer CLI that submits a
`subprocess.run(["bash","-c", cmd])` call to a registered Globus Compute
endpoint on Polaris / Crux and prints the returned
`{exit_code, stdout, stderr}` dict back to your terminal.

The script's shebang is `uv run --script`, so it self-installs its deps
(`globus-compute-sdk`, `typer`) into a uv cache on first run.

## When to use

- The user asks to "run X on Polaris/Crux" and either says
  *"use remote_bash"* or implies a synchronous one-shot (no need for the
  full IRI submit/poll/fetch dance).
- Quick env probes, `ls`/`find`/`module avail`/`which python`, single Python
  scripts that finish in well under the timeout.
- Driving an already-set-up analysis pipeline that just needs to be invoked.

Prefer `alcf-iri-job` instead when:
- The user explicitly says "IRI API" or wants the JobSpec path.
- The work is long-running and you'd rather queue + poll than block.
- You need to retrieve a file that wasn't already produced via stdout
  (`remote_bash` only returns stdout/stderr — files stay on the cluster).

## Auth

Globus Compute uses its own auth (Globus Auth tokens cached under
`~/.globus_compute/`). The first remote call in a session will block on an
interactive browser login if the cache is empty or expired. There is no
`$alcf_access_token` involvement — that's only for the IRI API.

If the user hits an auth error, tell them to run any `remote_bash.py` call
in a real terminal once to refresh the cache, then come back.

## Invocation

```
uv run ./remote-bash/remote_bash.py \
  --endpoint <polaris|crux> \
  --account  <project>          # default: datascience
  --queue    <queue>            # default: debug
  --cwd      <remote_dir>       # optional; defaults to endpoint's home
  --timeout  <seconds>          # default: 300; killed remotely after this
  --venv     <conda/venv path>  # default: /opt/globus-compute-agent/venv-py313
  "<bash command>"
```

Endpoint IDs are hardcoded in the script (`EP_MAP`):

| name    | uuid                                       |
|---------|--------------------------------------------|
| polaris | 9a947ba5-f537-4681-acf3-cc66485aadec       |
| crux    | d01d0c83-e570-4977-9170-1b8f2316e7c6       |

## What it returns

The CLI prints a single Python repr of `{"exit_code": int, "stdout": str,
"stderr": str}` to stdout. Both streams are truncated to stay under a 10 MB
serialization limit, with the larger stream getting proportionally more
budget. Truncation footers look like `[truncated — N bytes total]`.

Parse the result as a Python dict (`ast.literal_eval`) rather than treating
it as JSON — the script uses `print()` of the raw dict, so strings are
single-quoted Python style.

## Quoting and the `cmd` string

Whatever you pass becomes the argument to `bash -c` *on the remote*. That
means:

- The IRI/PBS GraphQL pitfalls from `alcf-iri-job` do **not** apply here —
  Globus Compute pickles the string and sends it intact, so `|`, `"`, `\n`,
  heredocs, escapes all survive. Write normal bash.
- The shell that runs `cmd` is a non-login `bash -c` (no `-l`), so
  `~/.bash_profile` is *not* sourced. If you need modules or conda, the
  command itself must source the right setup (e.g.
  `module use /soft/modulefiles && module load conda && source <env>`),
  OR rely on whatever the Globus Compute endpoint's worker has on PATH
  (the `--venv` flag controls that — points at a conda env that the
  endpoint activates before running user code).

## Gotchas

- **Timeout**: the `--timeout` is enforced both inside the remote
  `subprocess.run` and as `future.result(timeout=timeout+10)` locally. If
  the remote job sits in PBS queue longer than `timeout`, the local future
  raises `TimeoutError`. Bump `--timeout` for queued workloads, or stick to
  `--queue debug`.
- **Resource allocation**: every invocation triggers a PBS submission via
  the endpoint config (`account`, `queue`). Even a 2-second `hostname`
  job consumes a queue slot. Don't loop this for polling.
- **Working directory**: `--cwd` defaults to the endpoint's PBS working
  dir (usually `$HOME`). Pass an absolute path if you need to write
  somewhere specific.
- **Files stay remote**: stdout/stderr come back; nothing else. To pull
  a file, either include `base64 FILE` in your command and decode locally,
  or scp it after the fact.
- **SDK/worker Python mismatch**: globus-compute-sdk warns if the local
  Python version differs from the endpoint worker's (e.g. SDK 3.12 vs
  worker 3.13). Usually harmless; if you see deserialization errors,
  match the local Python to the endpoint's.
- **Cosmetic shutdown trace**: the SDK may print a `RuntimeError: can't
  create new thread at interpreter shutdown` after the result has already
  been returned. The result is valid; ignore the trace.

## Dispatch

1. Construct the bash command you want to run, including any
   `module load` / `source` setup needed for the remote env.
2. Run `uv run ./remote-bash/remote_bash.py --endpoint <X> --account <Y> --queue <Z>
   "<cmd>"`.
3. Wait — the call blocks until PBS schedules the job, runs it, and
   returns the dict.
4. Parse the printed dict, show `stdout` (and `stderr` if non-empty) to
   the user, and report the exit code.

## Example — single-line hostname

```
uv run ./remote-bash/remote_bash.py \
  --endpoint polaris --account datascience --queue debug \
  "hostname && date"
```

## Example — env probe with module load

```
uv run ./remote-bash/remote_bash.py \
  --endpoint polaris --queue debug --timeout 600 \
  "module use /soft/modulefiles && module load conda && \
   source /eagle/Auriga/csimpson/setup_polaris.sh && \
   export LD_LIBRARY_PATH=/eagle/Auriga/bin/lib:\$LD_LIBRARY_PATH && \
   python -c 'import gadget; print(gadget.__file__)'"
```

## Example — running a non-trivial Python script

Heredocs work over Globus Compute (unlike IRI), but for scripts longer than
a few lines it's still cleaner to stage the script locally, base64-encode
it into the command, decode it remote-side, and run it:

```
PY_B64=$(base64 -i local_script.py | tr -d '\n')
uv run ./remote-bash/remote_bash.py \
  --endpoint crux --queue debug --timeout 1500 \
  "module use /soft/modulefiles && module load conda && \
   source /eagle/Auriga/csimpson/setup_polaris.sh && \
   export LD_LIBRARY_PATH=/eagle/Auriga/bin/lib:\$LD_LIBRARY_PATH && \
   echo '$PY_B64' | base64 -d > /tmp/run.py && python /tmp/run.py"
```

## What NOT to do

- Don't poll a long job with repeated `remote_bash` calls — each one is a
  fresh PBS submit. If you need to wait on something, do the wait inside
  the bash command (`while ...; do sleep 30; done`) and bump `--timeout`.
- Don't use this for jobs that don't fit in a single node / queue slot —
  for multi-node MPI or long allocations, write an IRI JobSpec via
  `alcf-iri-job` instead.
- Don't paste secrets into the `cmd` string — it's serialized through
  Globus Compute and lands in worker logs.
