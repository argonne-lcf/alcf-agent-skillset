---
title: "Globus Compute Multi-Node Fan-Out on Polaris and Crux"
name: alcf-globus-compute-multi-node
category: jobs
systems: [polaris, crux]
tags: [globus-compute, multi-node, mpiexec, place-scatter, blocks, gpu-binding, polaris, crux]
description: >
  How to spread Globus Compute workers across multiple physical nodes via
  the ALCF facility multiuser endpoint, and how blocks relate to PBS jobs
  and tasks. Covers the place=scatter requirement, MpiExecLauncher setup,
  block lifecycle (idle timeout, max_blocks), and the Polaris GPU-binding
  caveat. Load alongside alcf-globus-compute-multiuser-endpoints when the
  workload needs more than one node or you need to reason about why a job
  is queued / shut down / packed onto one host.
last_verified: "2026-06"
---

# alcf-globus-compute-multi-node — multi-node fan-out, blocks, GPU caveats

This skill builds on `alcf-globus-compute-multiuser-endpoints` (load that
first for the schema, template defaults, auth, and basic invocation). It
covers what you need to add or know once a workload outgrows a single node.

## Prerequisites

- `alcf-globus-compute-multiuser-endpoints` loaded — for endpoint UUIDs,
  schema, template, and auth.
- Comfortable reading PBS submit scripts and `$PBS_NODEFILE`.

## Key Facts

- **`MpiExecLauncher` alone is NOT enough** to spread workers across
  distinct physical nodes — you also need `place=scatter` via
  `scheduler_options`. Without it, all workers land on one host even with
  `nodes_per_block: 2`.
- **Blocks ≠ tasks ≠ PBS jobs.** One PBS job (one Parsl block) holds
  `nodes_per_block` nodes for `walltime` and runs many `gce.submit()`
  tasks concurrently. Only the first submit after idle teardown pays
  queue wait.
- **`max_blocks: 1` (default) serializes PBS jobs.** Raise `max_blocks`
  AND `min_blocks` to run multiple PBS jobs concurrently.
- **Polaris GPU binding is NOT exposed** through `user_endpoint_config` —
  the facility template doesn't pass `--available-accelerators` to the
  worker pool. Do per-worker GPU pinning inside your task function.
- **Crux has no GPUs.** GPU binding is N/A.

## Distributing workers across nodes

Parsl's `PBSProProvider` always renders `select=N:ncpus=1:system=<machine>`
in the submit script. Those small `ncpus=1` chunks are free to pack onto a
single physical host, so `$PBS_NODEFILE` ends up with duplicate hostnames,
the worker pool's `sort -u $PBS_NODEFILE` collapses to one line, and
`mpiexec -n WORKERCOUNT --hostfile $HOSTFILE ...` launches every worker on
that one node.

**Symptom:** `nodes_per_block: 2` still produces a `tasks per host`
histogram with a single hostname.

**Fix:** add `-l place=scatter` as its own qsub directive via
`scheduler_options`. PBS then honors the node count regardless of the
small chunk size.

Working config (Polaris or Crux — swap the endpoint UUID):

```python
config = {
    "account":          "datascience",
    "queue":            "debug",
    "nodes_per_block":  2,
    "max_workers_per_node": 4,
    "walltime":         "0:30:00",
    "launcher_type":    "MpiExecLauncher",
    "scheduler_options": "#PBS -l filesystems=home:eagle\n#PBS -l place=scatter",
}
```

Verified end-to-end with a 30-task fan-out (8 workers across 2 nodes) on
both Polaris and Crux — both nodes appear in `$PBS_NODEFILE` and tasks
split between them.

Notes on the `scheduler_options` value:

- **No outer quotes.** Plain Python string. Adding `"..."` wraps it in
  YAML quotes that survive into the rendered submit script and break PBS
  parsing.
- **Embedded `\n` becomes a real newline** in the rendered submit script,
  producing two `#PBS -l ...` lines.
- **You MUST re-include `filesystems=`.** Overriding `scheduler_options`
  drops the template default; without `filesystems=` qsub rejects with
  "`Resource: filesystems is required to be set`".
- **Do NOT try `select_options: "system=<machine>:place=scatter"`** —
  `place=` is not a select chunk attribute; qsub errors with
  "`Resource invalid in 'select' specification: place`".

`overrides` and `bind_cmd` (the `MpiExecLauncher`-conditional Jinja vars)
do not need to be set — leave them at their defaults. Set them only when
you need extra mpiexec flags for the worker-pool launcher itself.

## Blocks, jobs, and tasks

There are four distinct units of work, and none of them are 1-to-1:

- **Task** — one `gce.submit(fn, ...)` call. Pickled, shipped, run on one
  worker. Cheap; tens to thousands per block is normal.
- **Worker** — a process on a compute node that pulls one task off the
  endpoint's queue, runs it, pulls the next. `max_workers_per_node`
  controls how many per node.
- **Block** — Parsl's name for one PBS job. Holds `nodes_per_block` nodes
  for `walltime`. Bounded by `min_blocks`, `max_blocks` (defaults 0, 1).
- **PBS job** — what `qsub` submits. Exactly one per block. The rendered
  submit script lives at
  `~/.globus_compute/uep.<endpoint-uuid>.<uep-uuid>/submit_scripts/<jobname>`.

Runtime flow:

1. First `gce.submit()` after an idle endpoint triggers a PBS submit. You
   pay queue wait once.
2. Workers come up, register with the interchange, start pulling tasks.
   Concurrency = `nodes_per_block × max_workers_per_node`, capped by
   pending task count.
3. Subsequent submits reuse the same block — no new PBS submission — as
   long as they arrive while the block is alive.
4. When the task queue empties, an idle timer starts (`max_idletime`,
   default 240s). A task arriving before the timer expires reuses the
   block; otherwise the worker pool shuts down and the PBS job exits.
5. The next submit after shutdown triggers a fresh PBS submission.

Practical consequences:

- **A 30-task fan-out is one PBS job's queue cost**, not 30. Stop sizing
  client timeouts as if every submit re-queues.
- **`max_blocks: 1` (default) means strict serial PBS jobs.** For
  concurrent jobs (e.g. one GPU, one CPU-only) raise both `max_blocks`
  AND `min_blocks`.
- **`max_idletime` is a knob, not a cost.** Lower for spiky workloads,
  raise for chatty interactive sessions where queue wait dominates.
- **A "stuck" `gce.submit()` is almost always queue wait for the first
  block.** Bump `future.result(timeout=...)` to ≥600s for any cold start.

## GPU binding caveats

- **Polaris (NVIDIA A100):** the facility endpoint's template does NOT
  pass `--available-accelerators` to the process_worker_pool launcher, so
  per-worker GPU binding is not exposed through `user_endpoint_config`.
  Workers see all of a node's GPUs through CUDA, but Parsl/Globus Compute
  cannot pin one GPU per worker for you. If you need strict binding, do
  it inside your task function — e.g. set `CUDA_VISIBLE_DEVICES` from
  `os.environ["PARSL_WORKER_RANK"]` or set up MPS/cgroups yourself.
- **Crux (CPU-only AMD EPYC Rome):** no GPUs. GPU binding is N/A.

## Common Pitfalls

- **All tasks land on one host despite `nodes_per_block: 2`:** missing
  `place=scatter`. See "Distributing workers across nodes" above.
- **qsub: "Resource: filesystems is required to be set":** your
  `scheduler_options` override dropped the default `filesystems=` line.
  Re-include it.
- **qsub: "Resource invalid in 'select' specification: place":** you put
  `place=scatter` inside `select_options`. Move it to `scheduler_options`.
- **mpiexec: "unrecognized option '--ppn 1 --depth=64'":** you passed
  `overrides` with outer quotes and the whole blob arrived as one argv.
  Either drop the outer quotes or, simpler, omit `overrides` entirely —
  the template default works.
- **mpiexec: "Cannot place all ranks on node list":** you set `--ppn` to
  a value incompatible with `nodes × max_workers_per_node`. Drop `--ppn`;
  mpiexec will distribute ranks itself.
- **Job re-queues on every submit:** you're calling `Executor(...)` and
  exiting the `with` block per task. The `__exit__` tears down the
  block. Keep a single `Executor` open for the whole fan-out.

## See Also

- `alcf-globus-compute-multiuser-endpoints` — schema, template, auth,
  basic invocation, single-task examples
- `../systems/polaris/overview.md` / `../systems/crux/overview.md`
- https://globus-compute.readthedocs.io/en/latest/sdk/executor_user_guide.html
- https://parsl.readthedocs.io/en/stable/userguide/execution.html#blocks
