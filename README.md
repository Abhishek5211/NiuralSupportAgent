# Niural support agent — baseline

This branch preserves the earlier raw-tool implementation. Package/import paths
and a small terminal adapter have been normalized; the baseline agent logic is
retained. Use Conda base and install requirements.txt if needed.

Copy .env.example to .env and configure the original provider/models. Run
`python -m niural_support_agent` or open `notebooks/evaluation.ipynb`.

The current implementation is on `codex/support-agent`. Compare commits/branches
instead of creating version folders. This baseline has known counting failures
and a legacy payment-case context shortcut; it is retained for honest comparison,
not claimed as a reliable completed agent. No complete baseline score exists.
