# /// script
# dependencies = ["globus-compute-sdk", "matplotlib"]
# ///
"""
30-task hostname+sleep stress on the Crux facility multiuser Globus Compute
endpoint, using MpiExecLauncher across 2 physical nodes. Mirrors the
working config in crux_mpiexec_hello.py: `place=scatter` via scheduler_options
forces one chunk per physical node, and the embedded `\n` is rendered into
the submit script as a second #PBS -l line.
"""
from globus_compute_sdk import Executor
from globus_compute_sdk.serialize import ComputeSerializer, CombinedCode

CRUX = "d01d0c83-e570-4977-9170-1b8f2316e7c6"

def task(idx):
    import socket, time, random
    start = time.time()
    hn = socket.gethostname()
    sleep_s = random.uniform(1.0, 20.0)
    time.sleep(sleep_s)
    end = time.time()
    return {"idx": idx, "hostname": hn, "sleep": sleep_s,
            "start": start, "end": end}

config = {
    "account": "datascience",
    "queue": "debug",
    "nodes_per_block": 2,
    "max_workers_per_node": 4,
    "walltime": "0:30:00",
    "scheduler_options": "#PBS -l filesystems=home:eagle\n#PBS -l place=scatter",
    "launcher_type": "MpiExecLauncher",
}

print("submitting 30 tasks to Crux (MpiExecLauncher, 2 nodes x 4 workers) ...", flush=True)
with Executor(
    endpoint_id=CRUX,
    user_endpoint_config=config,
    serializer=ComputeSerializer(strategy_code=CombinedCode()),
) as gce:
    futures = [gce.submit(task, i) for i in range(30)]
    results = []
    for i, f in enumerate(futures):
        r = f.result(timeout=1800)
        results.append(r)
        print(f"  done {i+1}/30  host={r['hostname']}  sleep={r['sleep']:.1f}s", flush=True)

import json
with open("/tmp/crux_throughput_mpi.json", "w") as fh:
    json.dump(results, fh, indent=2)

hosts = {}
for r in results:
    hosts[r["hostname"]] = hosts.get(r["hostname"], 0) + 1
print("\ntasks per host:", hosts)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

t0 = min(r["start"] for r in results)
ends_rel = sorted(r["end"] - t0 for r in results)
counts = list(range(1, len(ends_rel) + 1))

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
ax1.plot(ends_rel, counts, marker="o", linewidth=2, color="tab:blue")
ax1.set_ylabel("cumulative tasks completed")
ax1.set_title("Crux throughput (MpiExecLauncher, place=scatter): 30 tasks, 4 workers x 2 nodes")
ax1.grid(True, alpha=0.4)

sorted_by_start = sorted(results, key=lambda r: r["start"])
host_list = sorted(set(r["hostname"] for r in results))
colors = plt.cm.tab10.colors
host_color = {h: colors[i % len(colors)] for i, h in enumerate(host_list)}
for i, r in enumerate(sorted_by_start):
    ax2.barh(i, r["end"] - r["start"], left=r["start"] - t0,
             color=host_color[r["hostname"]], edgecolor="black", linewidth=0.3)
ax2.set_ylabel("task index (by start order)")
ax2.set_xlabel("seconds since first task start")
ax2.grid(True, alpha=0.4, axis="x")
ax2.legend(
    handles=[plt.Rectangle((0,0),1,1, color=host_color[h], label=h) for h in host_list],
    loc="lower right", fontsize=8,
)

fig.tight_layout()
out = "/tmp/crux_throughput_mpi.png"
fig.savefig(out, dpi=120)
print(f"\nsaved plot: {out}")
print(f"total wall time: {max(ends_rel):.1f}s   ideal serial: {sum(r['sleep'] for r in results):.1f}s")
