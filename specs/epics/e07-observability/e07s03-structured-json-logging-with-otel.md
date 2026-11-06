# e07s03 — Structured JSON logging with OTel

**type:** feature
**risk:** P1
**context:** e07-observability
**bcps:** 2

## Context

Custom JsonFormatter: timestamp, level, message, module, attributes. OTel trace_id and span_id injected when span context is valid. Logs to stdout and file. setup_logging() configured in lifespan startup.

## Requirements

#### ADDED: Structured JSON logging with OTel
Custom JsonFormatter: timestamp, level, message, module, attributes. OTel trace_id and span_id injected when span context is valid. Logs to stdout and file. setup_logging() configured in lifespan startup.

## Acceptance Criteria

```gherkin
Feature: Structured JSON logging with OTel
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Structured JSON logging with OTel is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Structured JSON logging with OTel
   → verify: `python -c 'from grimoire.observability.logging import JsonFormatter, setup_logging'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.observability.logging import JsonFormatter, setup_logging'
```
