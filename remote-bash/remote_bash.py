#!/usr/bin/env uv run --script
# /// script
# dependencies = [
#   "globus-compute-sdk",
#   "typer",
# ]
# ///
def remote_bash(cmd, cwd=None, timeout=300):

    import subprocess, json, os

    LIMIT = 9_500_000  # slightly below 10MB limit


    def truncate(s, max_bytes):
        b = s.encode()
        if len(b) <= max_bytes:
            return s
        return b[:max_bytes].decode(errors="ignore") + f"\n[truncated — {len(b)} bytes total]"

    def fit(stdout, stderr):
        out_len = len(stdout.encode())
        err_len = len(stderr.encode())
        total = out_len + err_len
        if total <= LIMIT:
            return stdout, stderr

        ratio = out_len / total if total else 0.5
        stdout_budget = max(int(LIMIT * ratio), min(out_len, LIMIT // 10))
        stderr_budget = max(LIMIT - stdout_budget, min(err_len, LIMIT // 10))
        return truncate(stdout, stdout_budget), truncate(stderr, stderr_budget)

    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, timeout=timeout, cwd=cwd)
        stdout = r.stdout.decode(errors="replace")
        stderr = r.stderr.decode(errors="replace")
        rc = r.returncode
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or b"").decode(errors="replace")
        stderr = (e.stderr or b"").decode(errors="replace")
        stderr += f"\n[timed out after {timeout}s]"
        rc = 124

    stdout, stderr = fit(stdout, stderr)
    return {"exit_code": rc, "stdout": stdout, "stderr": stderr}

from globus_compute_sdk import Executor
from globus_compute_sdk.serialize import ComputeSerializer, CombinedCode
from typer import Typer
import sys

EP_MAP = {
    "polaris": "9a947ba5-f537-4681-acf3-cc66485aadec",
    "crux": "d01d0c83-e570-4977-9170-1b8f2316e7c6",
}

from enum import Enum

class Endpoint(str, Enum):
    polaris = "polaris"
    crux = "crux"


serializer = ComputeSerializer(strategy_code=CombinedCode())

app = Typer()

@app.command()
def main(
    command: str,
    cwd: str  | None = None,
    timeout: int = 300,
    account: str = "datascience", 
    queue: str = "debug", 
    venv: str = "/opt/globus-compute-agent/venv-py313", 
    endpoint: Endpoint = "polaris",
):
    config = {
        'max_retries_on_system_failure': 0,
        'account': account,
        'queue': queue,
        'worker_init': f"source {venv.rstrip('/')}/bin/activate",
    }
    endpoint_id = EP_MAP[endpoint]

    with Executor(endpoint_id=endpoint_id, user_endpoint_config=config, serializer=serializer) as gce:
        future = gce.submit(remote_bash, cmd=command, cwd=cwd, timeout=timeout)
        print("Submitted task to remote endpoint, waiting for result...", file=sys.stderr)
        print(future.result(timeout=timeout+10))

if __name__ == "__main__":
    app()
