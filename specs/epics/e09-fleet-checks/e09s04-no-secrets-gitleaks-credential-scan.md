# e09s04 — no-secrets: gitleaks credential scan

**type:** feature
**risk:** P1
**context:** e09-fleet-checks
**bcps:** 1

## Context

Scan for leaked credentials, tokens, and API keys using gitleaks.
Targets all repos via regex: ".*". Requires gitleaks in workspace PATH
(or installs it via the script). Severity: error — leaked secrets are a
critical security issue.


## Requirements

#### ADDED: no-secrets: gitleaks credential scan
Scan for leaked credentials, tokens, and API keys using gitleaks.
Targets all repos via regex: ".*". Requires gitleaks in workspace PATH
(or installs it via the script). Severity: error — leaked secrets are a
critical security issue.


## Acceptance Criteria

```gherkin
Feature: no-secrets: gitleaks credential scan
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When no-secrets: gitleaks credential scan is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — no-secrets: gitleaks credential scan
   → verify: `test -f data/checks/no-secrets.yaml`

## Verification

Run runnable verify commands:
```bash
test -f data/checks/no-secrets.yaml
```
