# e08s04 — API schema contract tests

**type:** test
**risk:** P1
**context:** infra
**bcps:** 3

## Context

FastAPI validates response schemas at runtime via Pydantic, but there are no tests that assert a full API response validates against its declared `response_model`. A missing field in a response model would only surface in production when that endpoint is hit. Contract tests catch these schema drift errors at build time.

## Requirements

#### ADDED: API response contract validation
For each major endpoint, populate the in-memory cache with known test data, make a request, and validate the response against the declared Pydantic response model using `model_validate()`. Catch missing fields, type mismatches, and extra fields.

## Steps

1. **Contract test for GET /api/repos** — Populate cache with a known `RepositoryStats`. Request `/api/repos`. Validate response against `RepoListResponse`. → verify: `uv run pytest tests/test_github/test_router.py -v -k "contract" | grep -c PASSED | xargs -I{} test {} -ge 1`

2. **Contract test for GET /api/repos/{owner}/{name}** — Populate cache with known stats. Request repo detail. Validate against `RepoDetailResponse`. → verify: `uv run pytest tests/test_github/test_router.py -v -k "contract" | grep -c PASSED | xargs -I{} test {} -ge 2`

3. **Contract test for GET /api/checks** — Set checks state with known `CheckDefinition` list. Request `/api/checks`. Validate response is a list of `CheckListItem`. → verify: `uv run pytest tests/test_checks/test_router.py -v -k "contract" | grep -c PASSED | xargs -I{} test {} -ge 1`

4. **Contract test for GET /api/checks/{slug}/results** — Persist a known `CheckResultRecord`, query results, validate against `CheckResultResponse`. → verify: `uv run pytest tests/test_checks/test_router.py -v -k "contract" | grep -c PASSED | xargs -I{} test {} -ge 2`

5. **Contract test for GET /api/actions** — Set actions state. Request list. Validate against `ActionListItem`. → verify: `uv run pytest tests/test_actions/test_router.py -v -k "contract" | grep -c PASSED | xargs -I{} test {} -ge 1`

6. **Contract test for GET /api/actions/{slug}/runs/{id}** — Persist a known `ActionRunRecord` + `ActionRunRepoRecord`, query run detail, validate against `ActionRunDetail`. → verify: `uv run pytest tests/test_actions/test_router.py -v -k "contract" | grep -c PASSED | xargs -I{} test {} -ge 2`

## Out of scope

- OpenAPI spec validation (separate concern, handled by FastAPI's `/docs`)
- Response header validation
- Error response contract tests (404, 409, etc.) — covered by existing router tests

## Risks

- **Test maintenance**: Contract tests break on every schema change. This is intentional — they're the canary for unintentional schema drift.
- **Test data setup**: Each test needs a populated cache or DB state. Mitigation: use existing fixture patterns from `test_web/conftest.py`.
