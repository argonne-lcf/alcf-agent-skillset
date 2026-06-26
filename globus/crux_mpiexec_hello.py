# /// script
# dependencies = ["globus-compute-sdk"]
# ///
"""
Minimal hello-world on the Crux facility multiuser Globus Compute endpoint
using MpiExecLauncher. Relies on the template's default `overrides`.
"""
from globus_compute_sdk import Executor
from globus_compute_sdk.serialize import ComputeSerializer, CombinedCode

CRUX = "d01d0c83-e570-4977-9170-1b8f2316e7c6"

def hello():
    import socket
    return f"hello from {socket.gethostname()}"

config = {
    "account": "datascience",
    "queue": "debug",
    "nodes_per_block":2,
    "walltime": "0:10:00",
    "scheduler_options": "#PBS -l filesystems=home:eagle\n#PBS -l place=scatter",
    "launcher_type": "MpiExecLauncher",
}

with Executor(
    endpoint_id=CRUX,
    user_endpoint_config=config,
    serializer=ComputeSerializer(strategy_code=CombinedCode()),
) as gce:
    print(gce.submit(hello).result())
