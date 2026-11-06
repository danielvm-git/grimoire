# e02s02 — ETag caching for conditional requests

**type:** feature
**risk:** P1
**context:** e02-github-service
**bcps:** 3

## Context

Persist ETag and Last-Modified per endpoint URL in CachedETag table. Send If-None-Match/If-Modified-Since on subsequent requests. 304 responses skip parsing and don't count against rate limit.

## Requirements

#### ADDED: ETag caching for conditional requests
Persist ETag and Last-Modified per endpoint URL in CachedETag table. Send If-None-Match/If-Modified-Since on subsequent requests. 304 responses skip parsing and don't count against rate limit.

## Acceptance Criteria

```gherkin
Feature: ETag caching for conditional requests
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When ETag caching for conditional requests is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — ETag caching for conditional requests
   → verify: `python -c 'from grimoire.database import CachedETag'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.database import CachedETag'
```
