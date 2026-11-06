# e03s02 — Git identity and commit signing configuration

**type:** feature
**risk:** P1
**context:** e03-workspace
**bcps:** 2

## Context

Configure user.name and user.email in bare repos from config.git. Set up GPG or SSH commit signing (commit.gpgsign, gpg.format, user.signingkey). Export GIT_AUTHOR_NAME/EMAIL, GIT_COMMITTER_NAME/EMAIL, GIT_SSH_COMMAND env vars.

## Requirements

#### ADDED: Git identity and commit signing configuration
Configure user.name and user.email in bare repos from config.git. Set up GPG or SSH commit signing (commit.gpgsign, gpg.format, user.signingkey). Export GIT_AUTHOR_NAME/EMAIL, GIT_COMMITTER_NAME/EMAIL, GIT_SSH_COMMAND env vars.

## Acceptance Criteria

```gherkin
Feature: Git identity and commit signing configuration
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Git identity and commit signing configuration is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Git identity and commit signing configuration
   → verify: `grep -q 'user.name' src/grimoire/workspace/manager.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'user.name' src/grimoire/workspace/manager.py
```
