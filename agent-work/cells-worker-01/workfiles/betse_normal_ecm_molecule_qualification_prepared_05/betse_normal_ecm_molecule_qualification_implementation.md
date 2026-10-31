# Reviewed molecule qualification runners

The prepared runner binds dispatch02 (44 IDs, 942 reference forms, 84 native
captures) and transport02 (60 IDs, 1306 forms, 102 native captures) as separate
rosters. It retains their original fixtures, source, comparisons, tolerances,
480-second command limits, 1 GiB scientific process-tree RSS allowance and
8 GiB host reserve. The new metadata reader has a 512 MiB process-tree allowance
and the original 120-second reader limit. Capture profile02 pins and all
existing byte/header/member/type/shape/hash/CRC/compression guards are required.
No capacity maximum or all-captures-fit claim is made.

`python -B betse_normal_ecm_molecule_qualification_runner.py plan` prints the
held plan. `start` detaches one sequential controller for explicitly selected
families. It returns the new output/PID without polling. The controller stops
on the first failed or incomplete group, retains its artifacts, and leaves the
remaining groups unrun. There is no retry or automatic scientific follow-up.

Both `start` and the internal `worker` require a separately authorized external
release JSON and its exact SHA256. That record must contain:

- `kind`: `cells.explicit_molecule_scientific_round_release@1`;
- `status`: `explicitly_released` and nonempty `user_request` provenance;
- the exact `runner_manifest_sha256` and selected `packet_manifests`;
- matching `families`, coordinated integer `cpu`, absolute exclusive `output`,
  and bounded `round_id`.

The invocation also requires `--requested-round`, `--release`,
`--release-sha256`, `--families`, `--cpu`, `--output`, and `--round-id`.
The present held source/metadata receipt supplies no release record. A request
without one is refused before a run directory or child process is created.

The resource supervisor reuses the existing `run_bounded` and descendant
sampler bodies verbatim, with small standalone stdlib timestamp/JSON adapters.
It avoids importing the ensemble/model implementation into the supervisor.
Scientific children use one coordinated CPU, one BLAS/OpenMP thread, no GPU,
the exact frozen source path, and a new bytecode/cache location. The original
packet and explicitly pinned interpreter/library sources are checked before
and after each group.

A metadata-only pytest plugin records its actual PID, start identity,
executable, affinity, loaded-file inventory and each setup/call/teardown
outcome with assertions enabled. Inherited Python optimization is overridden.
It also records actual conditional subprocess commands, input hashes, identities,
affinities and exits. The reader matches those records to the native/reference
output paths, requires exact unique unskipped JUnit IDs, and checks every loaded
file against the frozen source, runner or declared runtime-library pins.

The reader binds archives sequentially and keeps compact hashes and a bounded
cache of decoded metadata; it does not retain every complete buffer tree at once.
The reader requires the new baseline/dispatch/setup outcome archives wherever
capture02 writes them. It verifies complete original wrapper/cause chains,
partial material/cache/shared/publication fields, positional Frames, chemistry
insertion order, transporter prefixes and actual negative failure buffers.
It preserves scalar/zero-dimensional numeric equivalence and exact array
dtype/shape/value semantics, including signed zeros and array NaNs. Original
pytest assertions and numerical budgets remain unchanged. Initial dependency
admission controls use their original typed inputs and assertions; the plugin
adds complete child test outcomes without inventing absent setup producers.

Every reference pair needs its original complete comparison and both precision
forms. The reader checks the original normalized error limit 1 and resolution
limit 0.1, fresh reference status, actual child runtime, exact reference/native
counts and native pre-runtime raw captures. Missing/incomplete archives,
unrelated source failures, unexpected returns, stale profiles, skipped tests,
unbound loaded files and unresolved child processes cannot receive completion
credit. The metadata preparation performs no scientific imports, fixture/model
or reference evaluation, pytest collection, launch, or existing-job queries.
