# Task Graph

```text
repository integrity
  -> configuration + migrations + ownership
  -> listing + images + adapters
  -> validation + prepublish review
  -> jobs + worker + audit + emergency pause
  -> action center + manual completion + history
  -> tests + browser evidence + docs
  -> deployment evidence + human acceptance
```

The final node cannot be inferred from the earlier nodes. Passing local verification does not supply a target database, real provider credentials, backup restore, edge throttling, accessibility observation, non-technical user evidence, or launch ownership.

See `docs/TASK_GRAPH_AND_EXECUTION.md` for execution lanes and `docs/CODEX_CHECKPOINTS.md` for resumption state.
