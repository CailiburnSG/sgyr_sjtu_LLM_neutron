# B2：LLM 全库证据选择 + LLM 行动选择

B2 evaluates one complete, independent evidence-assisted precheck run:

```text
event combination X + fixed 300-card library
  -> LLM selects exactly K evidence IDs
  -> the same run supplies only those K full cards to the LLM
  -> LLM selects exactly one fixed action A1--A4
```

This is not free-form diagnosis.  The selector may only choose IDs from the
reviewed evidence library, and the action stage may only emit the established
precheck action contract.  `goldcard_id` and gold labels are evaluation-only
and never enter either prompt.

The full-library selector receives the same reviewed card information that is
available to B1 candidates: evidence text, source/location, `topic_tags`,
`applicability`, measurement scope/relevance and transfer limits.  It also
receives the fixed A1--A4 definitions so it can select evidence for the actual
precheck task.  It never receives a gold action or gold evidence IDs.

## Independence rule

Every `case x K x n x pool x repeat` is a fresh end-to-end run.  Its selected
evidence is consumed only by that same case's action call and is never reused
by another condition, pool, repeat, or case.  Two internal calls are used only
to avoid sending the full library again during action selection.

## First formal condition

The first planned condition is zero-shot `K=10`, with independent repeated
end-to-end runs.  Fixed-example conditions must regenerate evidence selection
for every pool and every validation case; they may not reuse zero-shot choices.

## Output layout

The official zero-shot output is stored as `notrain/<model>/top_k_XX/`, matching
the B1 zero-shot layout.  Its `run_id` remains in JSON/CSV as an audit field.
Development pilots live under `pilots/` and are not part of `notrain/`.
Each official result keeps raw nested JSON/JSONL and flat CSV statistics:

- `b2_run_metrics.csv`: combined and per-stage token totals plus action metrics;
- `b2_action_metrics.csv`: action-level precision, recall and F1;
- `b2_semantic_metrics.csv` / `b2_semantic_by_action.csv`: selected-evidence semantics;
- `b2_error_counts.csv`: selector and action-stage contract errors.

`notrain/summary_metrics.csv` is the cross-run index.  Pilot runs are visibly
marked by their case count and are never combined with the frozen 60-case run.

Earlier text/source-only runs that omitted reviewed metadata and action
definitions are retained under `ablations/`; they are not main B2 results.

## Fixed complete-golden few-shot subexperiments (prepared; not yet run)

Three sibling `with_training_*` directories keep the B2 variants. Their common
example pool is materialized from frozen B1 training-side case IDs, but the
model-visible example is ID-free and complete: event combination + the three
reviewed human evidence cards + fixed action + boundary note.

- `with_training_selector/` (B2-FS-R): complete examples enter the full-library
  selector only; the action call remains zero-shot.
- `with_training_action/` (B2-FS-A): the full-library selector remains zero-shot;
  complete examples enter the action call only.
- `with_training_both/` (B2-FS-RA): both calls receive the same complete
  examples, while each evaluation case still selects its own evidence afresh.

Every case/pool remains a fresh two-call end-to-end run. The selector's current
case evidence cannot be reused by either variant, another pool, or a later
repeat. The materializer and both runners expose `--validate-only`; this checks
the 60-case split, 300-card library, stage-local example injection, and absence
of `goldcard_id` and gold-evaluation fields in prompts before any API call.
