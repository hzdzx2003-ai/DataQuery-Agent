# Phase 1 Verified Results

> 历史记录 · 2026-09-22 / evaluation v2.0.1。下文保留该阶段原始表述；最新版代码、结果与范围见[版本与数据索引](VERSION_INDEX.md)，演进关系见[迭代历史](ITERATION_HISTORY.md)。


## Phase 3 development live run — 2026-09-22

- Scope: all five executable development cases; no holdout case was sent to the model.
- All five generated SQL queries passed the read-only guard and executed successfully on the first attempt.
- After offline comparison, all five results strictly match their Gold results under the documented numeric precision.
- D2-003 initially appeared as a mismatch because v2.0.0 Gold returned an unrequested internal `lease_id`; the three requested business rows were already correct. The Gold projection was corrected in v2.0.1, with v2.0.0 archived and holdout content unchanged.
- This is a five-case development result, not a general model-accuracy or holdout claim.

## Phase 2B smoke test — 2026-09-22

- Model calls: 3 total (two initial requests plus one targeted repair request).
- D2-001: first attempt executed safely and matched the Gold result.
- D2-004: first attempt executed safely but returned zero rows because the model used `2026-08` rather than the stored `2026-08-01` month format.
- After adding the field-storage convention, D2-004 returned six rows and matched Gold under the documented four-decimal ratio comparison.
- No holdout case was sent to the model.
- These are smoke-test observations, not a general accuracy claim.

## Phase 1 foundation

Verification date: 2026-09-22

## Data

| Table | Rows |
|---|---:|
| properties | 6 |
| units | 48 |
| tenants | 39 |
| leases | 40 |
| rent_payments | 626 |
| operating_expenses | 600 |
| **Total** | **1,359** |

## Evaluation

| Expected action | Cases |
|---|---:|
| execute | 8 |
| execute with disclosure | 2 |
| clarify | 8 |
| reject | 6 |
| **Total** | **24** |

All 10 Gold SQL queries executed successfully. Nine returned at least one row; one intentionally returned an empty result for the unsupported-city boundary case.

The v2 cases are split into 16 development cases and 8 holdout cases. Version 1.0.0 is archived and retired for routing claims after review found wording leakage.

Evaluation version: `2.0.1`  
`cases.json` SHA-256: `7c8ddd95e4a674bfa0a069412ae3ce8433f4ed8caafbf65b6569fb1f8d6a248c`

## Automated checks passed

- Foreign keys
- Project area capacity
- Non-overlapping leases
- Expired leases, 2026 starts, sequential leases and boundary end dates
- Historical occupancy differs from the current status snapshot
- At least one tenant leases multiple units
- Unit occupancy status against active leases
- Payment months inside lease dates
- Payment status against paid/due amounts
- Payment dates against status, due date and fixed as-of date
- Non-negative expense values
- Evaluation ID uniqueness and metric references
- Development / holdout split
- Required disclosure cues
- Dangerous write-operation rejection coverage
- Structured clarification options
- Frozen evaluation manifest hash
- Read-only Gold SQL shape
- Deterministic regeneration of all six CSV files
- Python syntax compilation
- Two negative tests prove overlap and payment-status guards fail correctly
- Secret-pattern scan

The Phase 1 checks validate the data and evaluation foundation. Phase 2A validates deterministic routing on the development set, Phase 2B provides a two-question smoke test, and Phase 3 adds a five-case development-only live run. None is a holdout or general accuracy claim.
