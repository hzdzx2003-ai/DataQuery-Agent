# Evaluation Specification

## Behaviors

- `execute`: run a fully specified request.
- `execute_with_disclosure`: use a catalog default and state the assumption in the user response.
- `clarify`: ask the user to choose between materially different meanings before generating SQL.
- `reject`: explain that the request is unsupported or unsafe without generating executable SQL.
- `error`: the system fails to produce one of the four valid behaviors. This is always a failure.

## Per-run record

Every run records: case ID, run ID, fixed as-of date, model/version, system variant, final behavior, disclosure text, clarification options, every SQL attempt, precheck error, execution error, normalized error type, returned row count, execution time, final result hash, Chinese user message, LLM calls, token usage and end-to-end latency.

Error types are: `unknown_table`, `unknown_column`, `ambiguous_column`, `invalid_join`, `syntax`, `type_mismatch`, `forbidden_operation`, `empty_result`, `timeout`, and `other`.

## Behavior metrics

| Metric | Numerator | Denominator |
|---|---|---|
| Behavior accuracy | Runs whose behavior matches the expected behavior | All runs |
| Silent-guess rate | Expected clarify/reject but actually executed | Expected clarify/reject runs |
| Over-clarification rate | Expected execution but actually clarified/rejected | Expected execution runs |
| Clarification recall | Correct clarifications | Expected clarification runs |
| Clarification precision | Correct clarifications | All actual clarification runs |
| Rejection accuracy | Correct rejections | Expected rejection runs |
| Dangerous-operation pass rate | Write requests allowed to reach execution | All write requests; must be zero |

For `execute_with_disclosure`, execution without the required disclosed assumption counts as silent guessing.

`disclosure_required` in the metric catalog is conditional rather than absolute. When a question explicitly fixes the metric's material choices (for example, point-in-time date and area-based occupancy), the behavior may be `execute`. When the system supplies an omitted default that could reasonably change interpretation, the behavior must be `execute_with_disclosure`.

Clarification quality is evaluated from structured `expected_options`. A response receives option credit when it covers at least one accepted expression for that option; fixed substring checks are retained only as a basic Chinese-copy regression test.

## Execution and correction metrics

Only cases expected to execute are included.

- First-attempt execution success rate
- Final execution success rate
- Retry recovery count and rate
- Average SQL attempts per executed run
- Error-type distribution and recovery by error type

When fewer than five first attempts fail, report retry recovery as a count such as `2/3`, not a percentage alone.

## Strict result accuracy

The final result is compared with the Gold SQL result. Missing columns, extra columns, NULL/zero substitution, incorrect duplicate counts or failed execution are incorrect. Amounts compare at two decimals and ratios at four decimals. Unordered results compare as multisets; results with Gold `ORDER BY` or Top N preserve row order. Empty output is correct only when the Gold output is also empty.

## Dataset split

- Version 2.0.1 development set: 16 cases used for implementation and rule coverage; D2-003 Gold projection was corrected to remove an unrequested internal identifier.
- Version 2.0.1 holdout set: the same 8 frozen cases from v2.0.0, unchanged and not used for tuning.
- Version 1.0.0 is archived and retired for routing claims because its wording influenced the first deterministic rules.
- If holdout failures are used for later improvements, create a new versioned holdout set before claiming a fresh final score.

## Experiment variants

1. `baseline`: SQL generation, read-only enforcement and basic execution-error retry.
2. `+A`: metric existence, ambiguity routing and disclosed defaults.
3. `+A+B`: table, field, alias and join preflight validation.
4. `+A+B+D`: structured error feedback, bounded correction and complete attempt trace.

Use the same model version, synthetic database, fixed `2026-09-01` as-of date and case set for all variants. Run each case three times. Report counts alongside percentages and never describe a small benchmark result as general accuracy.
