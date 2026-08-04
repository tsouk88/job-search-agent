"""Turn a Harbor job into a build verdict.

Harbor exits 0 whether the code passed or failed — the reward lives in
result.json. This separates the three outcomes that matter, because they need
different reactions: a failed eval means the filter changed behaviour, an
errored trial means the harness never ran and says nothing about the code.

Exit codes: 0 pass, 1 eval failed, 2 infrastructure error.
"""

import json
import sys
from pathlib import Path

job_dir = Path(sys.argv[1])
result_path = job_dir / "result.json"
if not result_path.exists():
    print(f"infrastructure error: {result_path} was never written")
    sys.exit(2)

result = json.loads(result_path.read_text(encoding="utf-8"))
stats = result["stats"]

errored = stats["n_errored_trials"] + stats["n_cancelled_trials"]
incomplete = result["n_total_trials"] - stats["n_completed_trials"]
if errored or incomplete:
    print(f"infrastructure error: {errored} errored/cancelled, {incomplete} never completed")
    sys.exit(2)

failed = []
for eval_name, eval_stats in stats["evals"].items():
    for reward, trials in eval_stats["reward_stats"]["reward"].items():
        if float(reward) != 1.0:
            failed.extend((eval_name, trial, reward) for trial in trials)

for eval_name, trial, reward in failed:
    print(f"FAILED {eval_name} / {trial}: reward {reward}")
    stdout = job_dir / trial / "verifier" / "test-stdout.txt"
    if stdout.exists():
        lines = [line for line in stdout.read_text(encoding="utf-8", errors="replace").splitlines()
                 if line.startswith(("FAILED", "E "))]
        print("\n".join(lines[:20]))

if failed:
    sys.exit(1)

print(f"all {stats['n_completed_trials']} trial(s) passed")
