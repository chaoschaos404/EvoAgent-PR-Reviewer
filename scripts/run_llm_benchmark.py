"""Score the 100-case PR diff benchmark with a configured OpenAI-compatible LLM reviewer.

Uses the same harness, dataset and matching rules as scripts/run_e2e_evaluation.py;
only the reviewer under test changes. Configure the model through the standard
custom-provider variables (EVOAGENT_LLM_BASE_URL / EVOAGENT_LLM_API_KEY /
EVOAGENT_LLM_MODEL) or a .env file before running.
"""
import argparse
import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evoagent.config import Settings, load_dotenv  # noqa: E402
from evoagent.evaluation_harness import (  # noqa: E402
    EndToEndEvaluationHarness,
    load_jsonl,
)
from evoagent.reviewer import OpenAICompatibleReviewer  # noqa: E402


# Review policy handed to the model: one rule id per risk class, with the severity
# the project assigns to it. Matching in the harness compares CWE identities derived
# from these rule ids, so the taxonomy keeps LLM output comparable to rule reviewers.
RULE_TAXONOMY = [
    ("SEC-EVAL", "critical", "eval()/exec() or other dynamic code execution on external data"),
    ("SEC-PICKLE-LOAD", "high", "deserializing untrusted data with pickle.loads/marshal"),
    ("SEC-YAML-LOAD", "high", "yaml.load without SafeLoader on untrusted input"),
    ("SEC-SUBPROCESS-SHELL", "high", "shell=True or shell invocation with interpolated arguments"),
    ("SEC-HARDCODED-SECRET", "high", "literal credential assigned in code; values read from os.environ or secret managers are safe, obvious non-secret placeholders such as test-placeholder/example/dummy are safe"),
    ("SEC-SQL-CONCAT", "high", "SQL built by string concatenation or formatting; parameterized queries with placeholders are safe"),
    ("SEC-PATH-TRAVERSAL", "high", "opening user-controlled paths without confinement to a base directory"),
    ("SEC-OPEN-REDIRECT", "medium", "redirecting to a user-supplied URL without an allowlist"),
    ("SEC-ASSERT-AUTH", "medium", "authorization enforced with assert instead of an explicit check"),
    ("SEC-INSECURE-COOKIE", "medium", "cookie set with secure=False; secure=True is safe"),
    ("SEC-WEAK-HASH", "medium", "md5/sha1 applied to external or user-controlled data; hashing a fixed constant for a fixture id is safe"),
    ("SEC-WEAK-RANDOM", "medium", "non-cryptographic random used for tokens or security values"),
    ("SEC-INSECURE-TEMPFILE", "medium", "predictable temporary file creation such as tempfile.mktemp"),
    ("SEC-LOG-FORGING", "low", "logging user-controlled input without sanitization"),
    ("REL-EMPTY-EXCEPT", "medium", "bare or except Exception: handler that swallows all failures; catching a specific exception is safe"),
    ("REL-UNBOUNDED-RETRY", "medium", "while True retry/loop without a maximum attempt bound"),
    ("REL-BLOCKING-ASYNC", "medium", "blocking call such as time.sleep inside async code"),
    ("REL-NONATOMIC-WRITE", "medium", "state file written directly with open().write() instead of atomic replace"),
    ("REL-FLOAT-MONEY", "medium", "float arithmetic used for monetary amounts"),
    ("REL-NAIVE-DATETIME", "medium", "naive datetime.now() used for expiry or timestamps"),
    ("REL-DEBUG-PRINT", "low", "debug print/console.log left in production code paths"),
]

SYSTEM_PROMPT = (
    "You are a senior secure code reviewer scoring unified diffs. Report only actionable "
    "defects introduced by added lines; ignore style preferences and untouched code. "
    "Classify each defect with exactly one rule_id from this policy taxonomy "
    "(rule_id, severity, meaning): "
    + "; ".join("%s / %s / %s" % item for item in RULE_TAXONOMY)
    + ". Use the taxonomy severity for the finding. path is the changed file path without "
    "a/ or b/ prefixes and line is the new-file line number of the added line that introduces "
    "the defect. If the diff introduces no defect, return an empty findings list. "
    'Return JSON only: {"findings":[{"rule_id":"...","severity":"critical|high|medium|low",'
    '"title":"...","explanation":"...","path":"...","line":1,"evidence":"...","fix":"...",'
    '"test":"...","confidence":0.0}]}'
)


def percent(value):
    return "%.1f%%" % (100 * value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", default=os.path.join(ROOT, "evaluation_data", "pr_diff_100.jsonl")
    )
    parser.add_argument(
        "--output-dir", default=os.path.join(ROOT, "output", "evaluation")
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Score only the first N cases (smoke test); 0 means the whole dataset.",
    )
    args = parser.parse_args()

    load_dotenv()
    llm = Settings.from_env().resolved_llm()
    if not llm:
        raise SystemExit(
            "no LLM configured; set EVOAGENT_LLM_BASE_URL, EVOAGENT_LLM_API_KEY "
            "and EVOAGENT_LLM_MODEL (or EVOAGENT_LLM_PROVIDER with its key)"
        )
    cases = load_jsonl(args.dataset)
    if args.limit:
        cases = cases[: args.limit]

    reviewer = OpenAICompatibleReviewer(
        base_url=str(llm["base_url"]),
        api_key=str(llm["api_key"]),
        model=str(llm["model"]),
        timeout=120,
        system_prompt=SYSTEM_PROMPT,
        provider=str(llm["provider"]),
        extra_headers=dict(llm.get("headers") or {}),
    )
    result = EndToEndEvaluationHarness().run(reviewer, cases, reviewer.name)

    metrics = result["metrics"]
    errors = [
        (item["id"], item["error"]) for item in result["case_results"] if item["error"]
    ]
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "llm-benchmark-report.json")
    with open(json_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    print("reviewer:", result["reviewer"])
    print("cases:", metrics["cases"], "(%d risk, %d clean)" % (
        metrics["risk_cases"], metrics["clean_cases"]))
    print(
        "precision=%s recall=%s F1=%s"
        % (percent(metrics["precision"]), percent(metrics["recall"]), percent(metrics["f1"]))
    )
    print(
        "high-risk recall=%s clean accuracy=%s severity accuracy=%s"
        % (
            percent(metrics["high_risk_recall"]),
            percent(metrics["clean_accuracy"]),
            percent(metrics["severity_accuracy"]),
        )
    )
    print(
        "execution success=%s TP/FP/FN=%d/%d/%d"
        % (
            percent(metrics["execution_success_rate"]),
            metrics["tp"], metrics["fp"], metrics["fn"],
        )
    )
    for split in ("validation", "holdout"):
        part = result["by_split"][split]
        print(
            "%s: F1=%s high-risk recall=%s clean accuracy=%s"
            % (
                split, percent(part["f1"]),
                percent(part["high_risk_recall"]), percent(part["clean_accuracy"]),
            )
        )
    if errors:
        print("failed cases: %d/%d" % (len(errors), metrics["cases"]))
        for case_id, error in errors[:5]:
            print("  %s: %s" % (case_id, error))
    print("report:", json_path)


if __name__ == "__main__":
    main()
