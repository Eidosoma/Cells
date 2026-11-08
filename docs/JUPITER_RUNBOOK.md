# JUPITER runbook

Step-by-step commands for taking a Cells GPU ensemble from the local L4 to one
JUPITER node and then to N independent one-node jobs. Written for an agent on a
JUPITER login node; every block is meant to be pasted as is after step 2.

Status, 8 November 2026: the scripts below were exercised on the local L4
(x86_64). Nothing here has run on JUPITER yet; the last section lists what is
unverified. These steps check the platform and the runner. Moving from L4/x86
to GH200/Arm still needs fresh numerical qualification of the chosen model.

| File | Purpose |
| --- | --- |
| `validation/ensemble/jupiter_env_setup.sh` | Python 3.13 venv with the L4's exact jax 0.11.1 / CUDA 13 wheel set |
| `validation/ensemble/jupiter_check.py` | `check` (devices, float64, JIT benchmark, CPU/GPU model screen), `smoke` (plan, run, pause, resume, status), `definition` |
| `validation/ensemble/jupiter.sbatch` | One node: `run`, `resume`, `check`, `smoke` |
| [GPU ensembles](GPU_ENSEMBLES.md) | Runner semantics: arms, batches, telemetry, pause/resume |

## Site facts behind the commands

- A Booster node has four GH200 superchips: an H100 with 96 GB HBM3 plus a
  72-core Grace CPU with 120 GB LPDDR5X each (288 Arm cores per node), aarch64,
  RHEL 9. Slurm runs through psslurm since 2026-08-27.
- Partition `booster`: 12 h maximum, 1 h default. Development work uses
  `--reservation=develbooster` (8 nodes; at most 4 nodes per job, 4 jobs per
  user, 120 minutes).
- Nodes are charged whole (nodes x wall time, whatever the GPU count): the
  budget of 10,000 GPU-hours is 2,500 node-hours.
- Compute nodes have no internet. Login nodes are shared (at most 20 processes
  and 25% of memory per user) and cannot open outgoing SSH connections.
- `$SCRATCH` deletes files 90 days after last use. Code and the venv go in
  `$PROJECT`, which compute nodes mount.
- Software stage 2026 provides Python 3.13.5 (the same as the local venv),
  GCC 14.3.0 and CUDA/13 (13.0.0). The NVIDIA driver supports CUDA 13 since
  2025-08-28. Cells uses NVIDIA's pip CUDA 13 wheels, not the CUDA module.

Sources: [JUPITER documentation](https://apps.fz-juelich.de/jsc/hps/jupiter/)
(access, batch system, GPU computing, environment, stage changelog, known
issues), checked 8 November 2026.

## 1. Access (user)

The user needs a JuDoor account in the compute project, an Ed25519 key uploaded
in JuDoor with a `from="..."` clause listing the client addresses, and MFA
(TOTP) enabled. The key becomes active about 15 minutes after upload.

```bash
ssh <user>@login.jupiter.fz-juelich.de
uname -m                                   # expect aarch64
jutil env activate -p <project> -A <budget>
echo "$PROJECT $SCRATCH"
```

## 2. Session variables

Create the file once; source it at the start of every session.

```bash
mkdir -p "$PROJECT/$USER/cells"
cat > "$PROJECT/$USER/cells/env.sh" <<'EOF'
jutil env activate -p <project> -A <budget>
module --force purge
module load Stages/2026 GCC Python
export CELLS_BUDGET=<budget>
export CELLS_HOME=$PROJECT/$USER/cells
export CELLS_CHECKOUT=$CELLS_HOME/Cells
export CELLS_VENV=$CELLS_HOME/venv-gpu
export CELLS_PYTHON=$CELLS_VENV/bin/python
export CELLS_OUTPUT_ROOT=$SCRATCH/$USER/cells
export CELLS_LOGS=$CELLS_OUTPUT_ROOT/logs
EOF
source "$PROJECT/$USER/cells/env.sh"
mkdir -p "$CELLS_LOGS"
```

`CELLS_OUTPUT_ROOT` holds every run, log and JAX/CUDA cache; the runner refuses
outputs outside it. If the check in step 5 shows that compute nodes cannot write
to `$SCRATCH`, use `$PROJECT/$USER/cells-runs` instead.

## 3. Code

Outgoing SSH is blocked, so clone over HTTPS (a private repository needs a
GitHub token) or copy a bundle from the workstation.

```bash
git clone https://github.com/Eidosoma/Cells.git "$CELLS_CHECKOUT"
# Without a token, on the workstation:
#   git bundle create cells.bundle main
#   scp cells.bundle <user>@login.jupiter.fz-juelich.de:
# and then here:
#   git clone ~/cells.bundle "$CELLS_CHECKOUT"
git -C "$CELLS_CHECKOUT" log -1 --oneline
```

Updating the checkout later is safe for paused runs: they resume from the
source frozen into their own output directory (step 7).

## 4. Python environment (login node, about 10 minutes, 4 GB in `$PROJECT`)

```bash
bash "$CELLS_CHECKOUT/validation/ensemble/jupiter_env_setup.sh" "$CELLS_VENV"
"$CELLS_PYTHON" -c "import jax, jaxlib; print(jax.__version__, jaxlib.__version__)"
```

The script loads `Stages/2026 GCC Python`, creates the venv and installs, from
wheels only, the exact package set of the local L4 environment: jax, jaxlib,
jax-cuda13-plugin and jax-cuda13-pjrt 0.11.1, numpy 2.5.3, scipy 1.18.1, pytest
9.1.1, and the NVIDIA CUDA 13.4, cuDNN 9.26 and NCCL 2.31 wheels. Every pin has
a linux aarch64 cp313 wheel on PyPI. It then runs `pip check` and writes the
installed versions, interpreter, modules and checkout revision to
`$CELLS_VENV/cells-env.json`. Running it again changes nothing.

Do not load the `CUDA` module: CUDA paths in `LD_LIBRARY_PATH` override the
pip CUDA libraries. Use `CELLS_MODULES=none CELLS_BASE_PYTHON=/path/to/python3.13`
for a different interpreter.

If the login node is not aarch64 or cannot reach PyPI, download the wheels on a
host that can and install them on a compute node:

```bash
bash "$CELLS_CHECKOUT/validation/ensemble/jupiter_env_setup.sh" --download "$CELLS_HOME/wheels"
srun -A "$CELLS_BUDGET" -p booster --reservation=develbooster -N 1 -t 00:30:00 \
    env CELLS_WHEELHOUSE="$CELLS_HOME/wheels" \
    bash "$CELLS_CHECKOUT/validation/ensemble/jupiter_env_setup.sh" "$CELLS_VENV"
```

## 5. Platform check (first GPU job, under 15 minutes)

```bash
cd "$CELLS_CHECKOUT"
sbatch -A "$CELLS_BUDGET" --reservation=develbooster --time=00:15:00 --export=ALL \
    --output="$CELLS_LOGS/%x-%j.out" --error="$CELLS_LOGS/%x-%j.err" \
    validation/ensemble/jupiter.sbatch check "$CELLS_OUTPUT_ROOT/check-01.json"
squeue --me
```

When `sacct -X -j <jobid> --format=JobID,State,Elapsed,ExitCode` shows the job
has finished:

```bash
"$CELLS_PYTHON" - "$CELLS_OUTPUT_ROOT/check-01.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
print(r["status"], r["checks"])
for d in r["devices"]:
    print(d["kind"], d["float64"]["pass"], round(d["benchmark"]["dgemm"]["GFLOPs"]))
print(r["runner_affinity"])
print(r["model_screen"]["history_gpu_vs_cpu"])
PY
```

Expect `pass` with four GH200 devices, float64 preserved and the
`spatial_extracellular@2` GPU history within atol 2e-12 and rtol 2e-11 of the
Grace CPU run. `runner_affinity.all_groups_within_topology` should be `true`:
it means the runner pins each GPU's workers to cores of the Grace CPU attached
to that GPU (from `nvidia-smi topo -m`). The job log prints the checkout
revision, dirty state and GPU inventory. The L4 reference passed in 48 s with
a DGEMM rate of 434 GFLOP/s and a CPU/GPU maximum relative difference of 3.5e-15.

Then run the GPU unit tests on a GH200 node. They start the fresh numerical
qualification; they do not complete it.

```bash
srun -A "$CELLS_BUDGET" -p booster --reservation=develbooster -N 1 -t 00:30:00 \
    --cpus-per-task=72 bash -c 'cd "$CELLS_CHECKOUT" && PYTHONPATH=src CELLS_TEST_GPU=1 \
    "$CELLS_PYTHON" -B -m pytest -p no:cacheprovider -q --basetemp="$CELLS_OUTPUT_ROOT/pytest-$SLURM_JOB_ID" \
    tests/unit/test_gpu_execution.py tests/unit/test_ensemble.py \
    tests/unit/test_integrated_ensemble.py tests/unit/test_pool_ensemble.py'
```

On the L4 these took 141 s (33 passed). Pytest empties its `--basetemp`
directory first, so give every run a new one.

## 6. One-node smoke (under 30 minutes)

```bash
sbatch -A "$CELLS_BUDGET" --reservation=develbooster --time=00:30:00 --export=ALL \
    --output="$CELLS_LOGS/%x-%j.out" --error="$CELLS_LOGS/%x-%j.err" \
    validation/ensemble/jupiter.sbatch smoke "$CELLS_OUTPUT_ROOT/smoke-01"
```

The smoke freezes the checkout with `validation/source_snapshot.py`, then runs
plan, run, SIGUSR1 pause, resume and status. It uses two workers per GPU, 64
worlds per arm, and the qualified finest-step `spatial_extracellular@2` arms
`baseline` and `pump_release` from `configs/spatial_kinetic_cluster.json`
(32 tasks of 4 worlds). It compares paused-then-resumed worlds with
uninterrupted replicas. Read `smoke-01/result.json`: `status`, `checks`,
`timeline`, `first_leg` and `resume_leg` (utilization and GPU-hours),
`resume_exactness`. A failed check also writes `failure.json`. On the L4 it took
118 s; all checks passed and the resume was bitwise equal.

Test a scheduler-driven pause next. The first job runs out of time:
`--signal=B:USR1@240` pauses it 4 minutes before its limit, and the dependent
job resumes it.

```bash
"$CELLS_PYTHON" "$CELLS_CHECKOUT/validation/ensemble/jupiter_check.py" definition \
    --output "$CELLS_OUTPUT_ROOT/signal-def.json" --worlds-per-arm 1024 --batch-worlds 32 \
    --max-wall-seconds 3600
first=$(sbatch --parsable -A "$CELLS_BUDGET" --reservation=develbooster --time=00:08:00 \
    --export=ALL --output="$CELLS_LOGS/%x-%j.out" --error="$CELLS_LOGS/%x-%j.err" \
    validation/ensemble/jupiter.sbatch run "$CELLS_OUTPUT_ROOT/signal-def.json" \
    "$CELLS_OUTPUT_ROOT/signal-01")
sbatch -A "$CELLS_BUDGET" --reservation=develbooster --time=00:30:00 --export=ALL \
    --dependency=afterany:"$first" \
    --output="$CELLS_LOGS/%x-%j.out" --error="$CELLS_LOGS/%x-%j.err" \
    validation/ensemble/jupiter.sbatch resume "$CELLS_OUTPUT_ROOT/signal-01" \
    "$CELLS_OUTPUT_ROOT/signal-02"
```

`signal-01/paused.json` shows that the pause worked; `signal-02/completion.json`
shows that the resume worked. If `signal-01` completed instead, the GH200 was
faster than expected: repeat with `--time=00:06:00` for the first job. Larger
batches are not a fix, because they lengthen each window (section 7).

## 7. Pause, resume and status

- A pause request (scheduler signal, `scancel --signal=USR1 --batch <jobid>`,
  or SIGTERM) stops task assignment. Running batches are checkpointed at their
  next window boundary, and the job ends with `paused.json`.
- The runner kills workers 55 s after a pause request; a task killed this way
  is recorded as failed and the run cannot be resumed. Keep each window
  (`window_steps` x `batch_worlds` x step cost) well under 30 s.
- Resume only `paused` runs, always into a new directory:
  `sbatch ... jupiter.sbatch resume OLD NEW`. This uses the frozen `OLD/source`,
  so a newer checkout cannot change the code. Failed runs need a new run.
- Chain jobs with `--dependency=afterany:<jobid>`. A job that hits its time
  limit is not "ok", and a run killed at the limit has no terminal result and
  cannot resume.
- Status of any run:
  `PYTHONPATH="$OLD/source" "$CELLS_PYTHON" -m cells.ensemble status "$OLD"`.
- `allocated_gpu_hours` in `result.json` counts from `SLURM_JOB_START_TIME` for
  each job. Do not sum the two legs of one allocation; reconcile with
  `sacct`/KontView, since `sreport` reports wrong values on JUPITER.

## 8. N independent one-node jobs

The runner refuses `SLURM_JOB_NUM_NODES` other than 1 and cannot run one node's
share of a campaign. N nodes are therefore N independent campaigns, each with
its own definition, seed and output directory. World IDs restart at 0 in every
definition, so stochastic families must use distinct seeds. The deterministic
ionic replicas do not depend on the seed, but distinct seeds keep the
campaigns unambiguous.

```bash
N=4
TEMPLATE=$CELLS_OUTPUT_ROOT/signal-def.json      # replace with the chosen model's definition
mkdir -p "$CELLS_OUTPUT_ROOT/prod-01/defs"
"$CELLS_PYTHON" - "$TEMPLATE" "$CELLS_OUTPUT_ROOT/prod-01/defs" "$N" <<'PY'
import json, sys
data, folder, n = json.load(open(sys.argv[1])), sys.argv[2], int(sys.argv[3])
base = data["seed"]
for k in range(n):
    data["seed"] = (base + 1000003 * k) % 2**32
    with open(f"{folder}/def-{k}.json", "x") as stream:
        json.dump(data, stream, indent=2)
PY
for k in $(seq 0 $((N - 1))); do
    sbatch -A "$CELLS_BUDGET" --time=02:00:00 --export=ALL \
        --output="$CELLS_LOGS/%x-%j.out" --error="$CELLS_LOGS/%x-%j.err" \
        validation/ensemble/jupiter.sbatch run "$CELLS_OUTPUT_ROOT/prod-01/defs/def-$k.json" \
        "$CELLS_OUTPUT_ROOT/prod-01/node-$k"
done
```

JUPITER's documentation does not describe job arrays. The template supports
them (`%a` in its arguments becomes the array index); try `--array=0-1` once
before relying on it:

```bash
sbatch --array=0-$((N - 1)) -A "$CELLS_BUDGET" --time=02:00:00 --export=ALL \
    --output="$CELLS_LOGS/%x-%A_%a.out" --error="$CELLS_LOGS/%x-%A_%a.err" \
    validation/ensemble/jupiter.sbatch run "$CELLS_OUTPUT_ROOT/prod-01/defs/def-%a.json" \
    "$CELLS_OUTPUT_ROOT/prod-01/node-%a"
```

Estimate costs before production. A completed one-node run writes
`cost-profile.json`; `cells ensemble balance` turns it into a balanced
definition, and `plan --jupiter-nodes N` (1 to 4 nodes) projects node-hours
and GPU-hours offline:

```bash
export PYTHONPATH=$CELLS_CHECKOUT/src
"$CELLS_PYTHON" -m cells.ensemble balance DEF.json --profile RUN/cost-profile.json \
    --output "$CELLS_OUTPUT_ROOT/balanced.json" --allocated-gpus 4
"$CELLS_PYTHON" -m cells.ensemble plan "$CELLS_OUTPUT_ROOT/balanced.json" --jupiter-nodes 4
```

## 9. Telemetry

- Every run writes `gpu-utilization.jsonl` (nvidia-smi busy percent, memory and
  power each second for every allocated GPU). `result.json` summarises it in
  `full_job_utilization` and `after_all_workers_warmed`; the 70% target is
  advisory.
- GPU busy time is not SM activity. In the L4 smoke the GPU was busy 78-84% of
  the time after warm-up, while DCGM measured SM activity below 1%: the guarded
  `lax.map` ionic kernels are latency-bound. Measure SM activity on the GH200
  before committing production hours.
- Locally, `jupiter_check.py smoke --dcgm-root DIR` adds DCGM counters, which
  needs `sudo`. On JUPITER, find out what the node offers:
  `srun ... bash -c 'command -v dcgmi nsys ncu; dcgmi discovery -l'`. If
  `dcgmi` works, run `dcgmi dmon -e 1001,1002,1003,1005 -d 1000 > dcgm.log &`
  next to the runner in a copy of the batch script. Otherwise take a short
  `nsys profile --gpu-metrics-devices=all` capture of a pilot, or use the LLview
  job report (https://llview.fz-juelich.de, samples minutes apart).

## 10. Output collection

- Runs live in `$CELLS_OUTPUT_ROOT/<run>` and logs in `$CELLS_LOGS`. Each run
  directory holds `registration.json` (definition, plan, devices, source
  hashes), `result.json`, `completion.json`, `paused.json` or `failure.json`,
  `cost-profile.json`, `gpu-utilization.jsonl`, `source/` and `tasks/`.
- Never delete or reuse a failed run directory; start a new output directory
  and keep the evidence.
- Copy results to the workstation with a command run on the workstation, since
  JUPITER cannot connect out. Leave checkpoints behind unless they are needed:
  `rsync -av --exclude 'checkpoint*' <user>@login.jupiter.fz-juelich.de:<scratch path>/smoke-01 <local runs dir>/`
- Move what must outlive the 90-day scratch purge to `$PROJECT`.

## 11. GPU-hour budget

Allocation: 10,000 GH200 GPU-hours = 2,500 node-hours, charged per node.
Replace the estimates with measured `cost-profile.json` and `sacct` figures as
they arrive.

| Phase | Jobs (estimate) | Node-h | GPU-h | Share |
| --- | --- | ---: | ---: | ---: |
| Platform: check, unit tests, smoke, signal test | about 6 jobs of 0.25-0.5 h on develbooster | 3 | 12 | 0.1% |
| Pilot of the chosen model: one node, timing profile, balance, pause/resume at real sizes | about 4 jobs of 1 h | 4 | 16 | 0.2% |
| GH200 qualification: CPU/GPU parity on Grace/H100, refinement, restart exactness, SM activity | about 10 jobs of 1-2 h | 20 | 80 | 0.8% |
| Scale-out: 4 independent nodes, 2 h | 1 round | 8 | 32 | 0.3% |
| Production | measured campaigns | 2,215 | 8,860 | 88.6% |
| Reserve: failures, reruns, repairs | | 250 | 1,000 | 10.0% |
| **Total** | | **2,500** | **10,000** | **100%** |

For reference, the L4 smoke used 0.025 GPU-hours. On JUPITER the same smoke
costs at least one node for the whole job: about 0.5 node-hours (2 GPU-hours)
for a 30-minute job, whatever it uses.

## 12. Not verified without access

- Module names (`Stages/2026 GCC Python`), whether the login node is aarch64
  with PyPI access, and whether the venv works on compute nodes.
- psslurm support for `--signal=B:USR1@240`, `--gres=gpu:4`, `--export=ALL`,
  `SLURM_GPUS_ON_NODE`, `SLURM_JOB_END_TIME` and job arrays, and whether
  `CUDA_VISIBLE_DEVICES` reaches the batch step.
- GPU-to-Grace core numbering (the check reports it), whether compute nodes can
  write to `$SCRATCH`, and whether DCGM or Nsight are available.
- That the installed driver loads the CUDA 13.4 pip runtime (it needs at least
  580; JSC enabled CUDA 13 in August 2025). A driver older than the wheels'
  `ptxas` only slows compilation (JAX warns and compiles serially). If CUDA
  fails to load, pin the `nvidia-cuda-*` wheels to the driver's CUDA minor
  version in `jupiter_env_setup.sh` and record the change.
- Whether `git` exists on compute nodes; the smoke's source snapshot needs it.
- Any GH200 numbers: throughput, SM activity, compilation time and CPU/GPU
  agreement.
