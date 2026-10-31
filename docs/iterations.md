# Baseline record

# v1

- Main interface: `v1.ipynb`, one question at a time.
- Model: Groq `openai/gpt-oss-120b`.
- Six thin tools, project-root mock API/token validation, isolated chat histories.
- Judge is optional and manual. No automatic retries or saved run metadata.
- No complete benchmark score is claimed.

## Observations

Groq key/model access works. No-argument tool schemas needed a compatibility fix.
Full repeated documentation exceeded the 8K request allowance; the guide is now
omitted after account lookup. A previous headcount answer incorrectly said 15;
reference counts are 14 employees / 16 workers including contractors.
Strict judge JSON generation failed at the provider; the optional judge now requests
plain JSON text and validates it locally. It has not been rerun after this change.

Automatic runs were stopped at the user's request. Future evaluations are run
manually in the notebook. Record what worked, what failed, and one v2 hypothesis there.

Refactor: shared API client/auth/Pydantic models now live in project-root `mock_api/`.
The notebook and v1 tools use named methods; no live calls were made during this refactor.
