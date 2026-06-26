---
title: "Globus Data Transfer on ALCF Systems"
name: alcf-globus-data-transfer
category: storage
systems: [polaris, aurora, crux]
tags: [globus, data-transfer, dtn, eagle, flare, home, hpss, cli, sdk, guest-collection]
description: >
  How to move files in and out of ALCF storage (home, Eagle, Flare, HPSS) with
  Globus — the ALCF DTN endpoint names, the CLI workflow (`globus login` →
  `globus transfer` → `globus task wait`), the Python `globus_sdk` pattern,
  sync-level / encryption / verify-checksum semantics, guest collections on
  Eagle, and the Aurora `/home` proxychains caveat. Load when transferring data
  to/from ALCF filesystems or scripting transfers from an agent.
last_verified: "2026-06"
alcf_docs_url: "https://docs.alcf.anl.gov/data-management/data-transfer/using-globus/"
globus_docs_url: "https://docs.globus.org/cli/"
---

# alcf-globus-data-transfer — Move data to and from ALCF storage with Globus

Globus is the supported way to move large data in and out of ALCF
filesystems. It runs as a hosted service: you submit a transfer task,
Globus moves the bytes between the two endpoints' Data Transfer Nodes
(DTNs), retries on failure, and reports status. No bytes flow through
your laptop or login session unless one side is a Globus Connect Personal
endpoint on your own machine.

## Purpose

Use this skill when an agent needs to move files between ALCF storage
(home, Eagle, Flare, HPSS) and another endpoint — another HPC center,
S3, an institutional collection, or a personal Globus Connect Personal
collection. It covers the ALCF endpoint names, the CLI workflow, the
Python SDK pattern, the transfer semantics that actually matter for
correctness (sync level, verify-checksum, encryption), and the quirks
specific to ALCF (Aurora `/home`, Eagle guest collections, HPSS keytab).

For *compute* over Globus (executing Python functions on Polaris/Crux),
see `alcf-globus-compute-multiuser-endpoints` instead. That's a
different Globus service with different auth.

## Prerequisites

- A Globus Auth identity linked to an ALCF account. Log in to Globus
  via `https://www.globus.org` → "Use your existing organizational
  login" → "Argonne LCF", then authenticate with your ALCF
  username + CRYPTOCard/MobilePASS+ OTP.
- For CLI/SDK use, the `globus-cli` or `globus-sdk` package installed in
  the environment you're running from. The CLI itself works from any
  machine with network access — it does not have to run on ALCF.
- For HPSS transfers: a keytab file at `~/.hpss/.ktb_<userid>` on a
  Polaris login node. Without it, `alcf#dtn_hpss` will reject auth.
- For Eagle guest-collection management: a PI on the Eagle project.
  Proxies and members cannot create guest collections.

## Key Facts

- **ALCF mapped (DTN) collections — use the legacy names with the CLI;
  they resolve to the current UUIDs:**

  | Collection name   | Filesystem | Path root                                | Notes |
  |-------------------|------------|------------------------------------------|---|
  | `alcf#dtn_home`   | agile-home (Polaris/Crux/Sophia) | `/<username>`                 | Not for Aurora `/home`. |
  | `alcf#dtn_eagle`  | Eagle      | `/eagle/<project>` (== `/lus/eagle/projects/<project>`) | Backs guest collections. |
  | `alcf#dtn_grand`  | Grand      | `/grand/<project>`                        | Legacy; check that your project still has Grand. |
  | `alcf#dtn_flare`  | Flare (Aurora) | `/<project>` (== `/lus/flare/projects/<project>`) | Use this for Aurora project data. |
  | `alcf#dtn_hpss`   | HPSS tape archive | HSI-style paths                  | Requires `.hpss/.ktb_<userid>` keytab. |

  The Eagle mapped-collection UUID is `05d2c76a-e867-4f67-aa57-76edeb0beda0`
  (visible in the Globus web app URL). UUIDs for the others can shift — `globus endpoint search alcf#dtn_<name>` returns the current one.

- **Aurora `/home` is *not* on `alcf#dtn_home`.** Currently the only way
  to move data in/out of Aurora `/home` over Globus is to run a
  proxychains-wrapped Globus Connect Personal on an Aurora login node
  (see Examples). Aurora *project* data on `/flare` uses `alcf#dtn_flare`.

- **Auth model:** Globus Auth identity (browser login or device-code
  URL), cached as a refresh token under `~/.globus/` (CLI) or
  `~/.globus_sdk/` (SDK). Tokens auto-refresh; ConsentRequired errors
  on mapped collections need `globus session consent <scope>` (the
  error message gives the exact scope) before the transfer will
  succeed.

- **`globus transfer` is async.** It returns a task ID immediately and
  the bytes move in the background. Block with `globus task wait
  <task_id>` (exit 0 = success, non-zero = inactive/failed). Use
  `globus task show <task_id>` to inspect.

- **Sync levels (`--sync-level` CLI / `sync_level=` SDK):** higher
  levels skip more files but cost more to check. Pick the cheapest
  that's correct for your case.
  - `exists` / `0` — copy only if destination is missing.
  - `size`   / `1` — copy if size differs.
  - `mtime`  / `2` — copy if source mtime is newer.
  - `checksum` / `3` — copy if checksums differ. Slow; only when you
    don't trust mtime (e.g. rsync'd source whose mtime got reset).

- **Verify and encrypt are independent of sync level.**
  `--verify-checksum` re-reads both sides post-transfer and retries on
  mismatch; default off. `--encrypt-data` encrypts in flight; default
  off, but if either collection has `force_encryption` set, encryption
  happens regardless. Both slow the transfer; only set when you need
  them.

- **Paths are forward-slash, relative to the collection root**, even
  for Windows endpoints. For a recursive directory transfer, the source
  directory's *contents* are placed inside the destination directory;
  Globus creates the destination if it doesn't exist.

- **Use the CLI for ad-hoc transfers, the SDK for scripts.** The CLI is
  fine from a notebook or shell; the SDK is the right choice when you
  need batch items, filter rules, or programmatic monitoring. Both
  share the same task/queue on the server side.

- **Eagle guest collections** are how you share project data with
  non-ALCF collaborators. Only the PI can create one; access managers
  can grant permissions but not create. Writes by collaborators show
  up POSIX-owned by the PI.

## Examples

### CLI — one-shot recursive transfer with wait

```bash
# One-time login on the machine running the CLI.
globus login

# Resolve endpoint UUIDs (only needs to be done once; cache them).
SRC=$(globus endpoint search 'alcf#dtn_eagle' --filter-owner-id 'ALCF' \
        --jmespath 'DATA[0].id' --format=UNIX)
DST=<destination-collection-uuid>

# Submit a recursive transfer, capture the task ID, block until done.
TASK=$(globus transfer \
        "${SRC}:/eagle/myproject/runs/2026-06/" \
        "${DST}:/incoming/runs/2026-06/" \
        --recursive \
        --sync-level mtime \
        --label "myproject 2026-06 runs" \
        --jmespath 'task_id' --format=UNIX)

globus task wait "$TASK" --timeout 3600
globus task show "$TASK"
```

If `globus transfer` exits with status 4, Globus is asking for a
step-up consent; copy the `globus session consent ...` command from
the error message, run it, then retry.

### CLI — batch transfer from a file

```bash
# batch.txt — one item per line. --recursive optional per line.
# Each line:  [--recursive] SRC_PATH  DST_PATH
cat > batch.txt <<'EOF'
/eagle/myproject/checkpoints/step_10000.pt  /incoming/checkpoints/step_10000.pt
/eagle/myproject/logs/                       /incoming/logs/ --recursive
EOF

globus transfer "$SRC" "$DST" --batch batch.txt --label "ckpt + logs"
```

### Python SDK — scripted transfer with filter rules

```python
import globus_sdk

# Authorizer: prefer NativeAppAuthClient + refresh token in cache for
# headless use; for interactive scripts, ConfidentialAppAuthClient or
# the SDK's CLI-token reuse works too. See globus_sdk docs.
tc = globus_sdk.TransferClient(authorizer=authorizer)

EAGLE = "05d2c76a-e867-4f67-aa57-76edeb0beda0"   # alcf#dtn_eagle
DEST  = "<destination-collection-uuid>"

tdata = globus_sdk.TransferData(
    tc,
    source_endpoint=EAGLE,
    destination_endpoint=DEST,
    label="myproject 2026-06 runs",
    sync_level=2,            # mtime
    verify_checksum=False,   # turn on only when you don't trust mtime
    encrypt_data=False,
    preserve_timestamp=True,
)

tdata.add_item(
    source_path="/eagle/myproject/runs/2026-06/",
    destination_path="/incoming/runs/2026-06/",
    recursive=True,
)
tdata.add_filter_rule(method="exclude", type="file", name="*.tmp")
tdata.add_filter_rule(method="exclude", type="dir",  name="__pycache__")

task_id = tc.submit_transfer(tdata)["task_id"]
print("submitted", task_id)

# Poll. tc.task_wait blocks up to timeout, returns True on terminal state.
done = tc.task_wait(task_id, timeout=3600, polling_interval=15)
status = tc.get_task(task_id)["status"]
print(status)
```

### Aurora `/home` via Globus Connect Personal on a login node

`alcf#dtn_home` does not back Aurora. To move data in/out of Aurora
`/home`, run Globus Connect Personal *on an Aurora login node* through
proxychains, then transfer to/from that personal endpoint:

```bash
# One-time setup on a fresh Aurora login session. Make sure no proxy
# env vars are exported (comment out any proxy lines in ~/.bashrc).
/soft/tools/proxychains/bin/proxychains4 \
    -f /soft/tools/proxychains/etc/proxychains.conf \
    /soft/tools/globusconnect/globusconnect -setup --no-gui

# Paste the auth URL into a browser, complete the flow, paste the code
# back, name the endpoint (e.g. aurora_login_uan11).

# Then start it (backgrounded). Add -restrict-paths to expose Flare too.
/soft/tools/proxychains/bin/proxychains4 \
    -f /soft/tools/proxychains/etc/proxychains.conf \
    /soft/tools/globusconnect/globusconnect -start \
    -restrict-paths /home/$USER,/lus/flare/projects/<project> &
```

The personal endpoint then appears in the Globus web app under the
name you gave it, and you can transfer from `alcf#dtn_eagle` or any
other collection into it.

### HPSS — archive a directory via Globus

```bash
# Requires ~/.hpss/.ktb_$USER on a Polaris login node beforehand.
SRC=$(globus endpoint search 'alcf#dtn_eagle' --jmespath 'DATA[0].id' --format=UNIX)
HPSS=$(globus endpoint search 'alcf#dtn_hpss' --jmespath 'DATA[0].id' --format=UNIX)

globus transfer "${SRC}:/eagle/myproject/runs/2026-06/" \
                "${HPSS}:/home/$USER/myproject/runs_2026-06/" \
                --recursive --label "archive runs 2026-06"
```

## Common Pitfalls

- **"ConsentRequired" / CLI exits 4:** the mapped collection needs an
  extra scope. The error message includes the exact `globus session
  consent ...` command — run it and retry. This is one-per-collection
  per identity; it persists in the token cache.

- **`EndpointNotFound`:** typoed endpoint name, or the endpoint was
  retired/renamed. Run `globus endpoint search <name>` (e.g.
  `alcf#dtn_eagle`) to confirm the current UUID.

- **`PermissionDenied` on a guest collection:** the PI has not granted
  your Globus identity access, *or* your identity is not the one they
  shared with (Globus identities don't auto-link). Check the
  collection's Permissions tab in the web app; if you have multiple
  linked identities, the one the PI shared with must be the one signed
  in.

- **HPSS transfer fails with "keytab missing":** no
  `~/.hpss/.ktb_<userid>`. Email `support@alcf.anl.gov` to be enabled
  for HPSS — it's not on by default for new accounts.

- **Files transferred from a guest collection are owned by the PI on
  POSIX:** intentional. All reads/writes through a guest collection
  execute as the PI. If the PI lacks POSIX permission for a file,
  collaborators can't see it either, regardless of guest-collection
  ACL.

- **Aurora `/home` transfer "just hangs" with proxychains setup:** a
  proxy env var leaked from `~/.bashrc`. Open a fresh shell with proxy
  exports commented out before running the proxychains command.

- **`--sync-level checksum` is much slower than expected:** it checksums
  every file on both sides before deciding. Drop to `mtime` unless you
  have a specific reason to distrust timestamps (e.g. an rsync'd source
  whose mtimes were reset).

- **Recursive destination path "doubled up":** Globus places source
  directory *contents* under the destination directory. Trailing
  slashes do not change this — `src/foo/` → `dst/bar/` puts `foo`'s
  contents directly into `bar`, not `bar/foo`.

- **Transfer succeeds but file is wrong size at destination:** turn on
  `--verify-checksum` for the next attempt. Underlying GridFTP errors
  silently truncate in rare cases on flaky endpoints; checksum
  verification retries until it matches.

- **Submitting hundreds of items with a script and getting duplicates
  after a network hiccup:** make sure you're using the SDK's
  `TransferData` (which fetches a `submission_id`) or the CLI (which
  does the same). Resubmitting with the same `submission_id` is safe;
  resubmitting raw API calls is not.

## See Also

- `alcf-globus-compute-multiuser-endpoints` — running *code* on Polaris/Crux
  through Globus Compute (different service, different auth)
- `../iri/output-retrieval.md` — alternative for small stdout/stderr
  retrieval from a job
- https://docs.alcf.anl.gov/data-management/data-transfer/using-globus/
- https://docs.alcf.anl.gov/data-management/acdc/eagle-data-sharing/
- https://docs.alcf.anl.gov/aurora/data-management/moving_data_to_aurora/globus/
- https://docs.globus.org/cli/
- https://docs.globus.org/api/transfer/task_submit/
- https://globus-sdk-python.readthedocs.io/
