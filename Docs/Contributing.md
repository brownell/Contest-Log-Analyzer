# Engineering Standards & Contribution Guide

## 1. Core Philosophy
We are modernizing our version control workflow.
* **Git is the Source of Truth:** We do **not** use inline change logs, author names, or date stamps inside source files. The Git history is our official record.
* **The "Main" Branch is Sacred:** The `main` branch must always represent a stable state (or a stable Beta state).
* **Release vs. Development:** We separate the act of "saving work" (Commits) from the act of "publishing software" (Tags).

---

## 2. File Header Standard
All Python (`.py`) files must begin with the following standard header block.
**Note for AI Agents:** When creating new files, you **must** apply this template.

```python
# {filename}.py
#
# Purpose: {A concise, one-sentence description of the module's primary responsibility.}
#
# Author: {Author Name}
# Date: {YYYY-MM-DD}
# Version: {x.y.z-Beta}
#
# Copyright (c) {Year} Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          ([https://www.mozilla.org/MPL/2.0/](https://www.mozilla.org/MPL/2.0/))
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0.
# If a copy of the MPL was not distributed with this
# file, You can obtain one at [http://mozilla.org/MPL/2.0/](http://mozilla.org/MPL/2.0/).
```

---

## 3. Versioning Strategy (SemVer)
We follow **Semantic Versioning 2.0.0**.

### The Beta Lifecycle
* **Format:** `1.0.0-beta.X`
    * Correct: `1.0.0-beta.1`, `1.0.0-beta.2`, `1.0.0-beta.10`
    * Incorrect: `1.0.0-beta1` (Missing dot breaks sorting), `1.0.1` (Do not bump Patch/Minor yet).
* **Rule:** We do not increment the Major, Minor, or Patch numbers during this phase. We only increment the **Prerelease Identifier**.

### The Release Lifecycle
* **Release Candidate:** `1.0.0-rc.1` (Used for verifying stability before Gold).
* **Gold Release:** `1.0.0` (No suffix).

---

## 4. Commit Message Standard (Angular)
We use the strict **Angular Convention**. This structure is mandatory for the final commit that lands on `main`.

### The Structure
```text
<type>(<scope>): <short summary>
  │       │             │
  │       │             └─⫸ Imperative, lowercase, < 50 chars
  │       └─⫸ Optional: (api), (auth), (db)
  └─⫸ See list below

<BLANK LINE>  <-- MANDATORY

<body>
  │
  └─⫸ Detailed explanation. Bullet points allowed.
      Wrap text at 72 chars.

<BLANK LINE>  <-- MANDATORY

<footer>
  │
  └─⫸ Optional. ONLY for "BREAKING CHANGE" or issue tracking.
```

### Allowed Types
| Type | Description | SemVer Impact |
| :--- | :--- | :--- |
| **feat** | A new feature for the user. | **MINOR** |
| **fix** | A bug fix for the user. | **PATCH** |
| **docs** | Documentation only changes. | None |
| **style** | Formatting (no code change). | None |
| **refactor** | Refactoring production code. | None |
| **perf** | A code change that improves performance. | **PATCH** |
| **test** | Adding/correcting tests. | None |
| **build** | Build system changes. | None |
| **ci** | CI configuration changes. | None |
| **chore** | Miscellaneous changes. | None |

### Handling BREAKING CHANGES
If a commit breaks backward compatibility, the Footer **must** be the very last section, preceded by a blank line.
```text
feat(api): rename user response fields

BREAKING CHANGE: API consumers accessing `userName` will now fail.
```

---

## 5. Git Workflow Manual (Human & AI)

### A. Feature Development (The Standard Path)
All work happens in branches. We do not commit to `main`.

1.  **Branch:** `git checkout -b feat/user-dashboard`
2.  **Work:** Commit frequently (`git commit -m "wip"`).
3.  **Merge (Squash):** We squash all branch commits into one clean commit on `main`.
    ```bash
    # 1. Switch to main
    git checkout main
    git pull

    # 2. Merge with Squash (Staging the changes)
    git merge --squash feat/user-dashboard

    # 3. Commit with the Strict Angular Standard
    git commit
    # (Editor opens: write "feat(dashboard): add user dashboard...")
    ```

### B. Hotfix Workflow (Emergency)
Used when a critical bug is found in a released version (e.g., `v1.0.0`), but `main` already contains new, unstable features.

1.  **Time Travel:** Checkout the specific release tag.
    `git checkout v1.0.0`
2.  **Branch:** Create a hotfix branch.
    `git checkout -b hotfix/security-patch`
3.  **Fix:** Fix the bug and commit.
    `git commit -m "fix(security): resolve auth bypass"`
4.  **Tag:** Tag the hotfix immediately.
    `git tag v1.0.1`
5.  **Push:** Push the tag to deploy.
    `git push origin v1.0.1`
6.  **Backport (Critical):** Merge the fix back into `main` so it isn't lost.
    ```bash
    git checkout main
    git merge hotfix/security-patch
    # Resolve conflicts if `main` has changed significantly.
    ```

### C. LTS / Support Workflow (Enterprise)
Used for customers stuck on old versions (e.g., v1.0) while we are working on v2.0.

* **Rule:** **Upstream First.** Never fix a bug in the support branch first.
* **Workflow:**
    1.  Fix the bug on `main` and commit (Hash: `A1B2C3`).
    2.  Checkout the support branch: `git checkout support/v1.0.x`.
    3.  **Cherry Pick:** `git cherry-pick A1B2C3`.
    4.  Tag the support release: `git tag v1.0.5`.

---

## 6. AI Agent Prompt Library

Copy these prompts to instruct your AI agent on the correct protocols.

**Prompt: Commit Message Generation**
> "Write a git commit message following the strict Angular Conventional Commits standard. Use one of these types: feat, fix, docs, style, refactor, perf, test, build, ci, chore. The subject must be lowercase and imperative. If the commit touches multiple files, list the changes in the body using bullet points. If there is a breaking change, use the 'BREAKING CHANGE:' footer format with a mandatory blank line before it."

**Prompt: File Creation**
> "When generating the new Python file, please ensure you include the standard project header block with the Copyright, License (Mozilla Public License 2.0), and Revision History sections."

**Prompt: Hotfix Guidance**
> "I need to perform a Hotfix on version `v1.0.0`. Please give me the CLI commands to checkout that tag, create a branch named `hotfix/my-fix`, and after I commit, show me how to tag it as `v1.0.1` and merge it back into `main`."