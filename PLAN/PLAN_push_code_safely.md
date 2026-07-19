# PLAN — Push Code Safely to Destination Repository

## SECTION A — GOAL DEFINITION

1. **What is being built or changed?**
   - Update `.gitignore` to prevent temporary or non-essential test/UI audit artifacts from being tracked.
   - Stage and commit all active code changes in the working directory that are useful and related to the main pipeline.
   - Push all commits (including past commits and new commits) safely to the target GitHub repository (`https://github.com/Shreyash-deve7/medical-ocr-pipeline.git`).

2. **What does "done" look like?**
   - All pipeline-related modifications and new configurations/scripts are staged and committed.
   - Temporary artifacts (`playwright-report/`, `test-results/`, `ui-audit-screenshots/`, `result.json`) are ignored and not pushed.
   - `git status` shows no pending modifications/untracked files (except for explicitly ignored ones).
   - All commits are successfully pushed to `dest main` branch.

3. **What is explicitly out of scope for this task?**
   - Writing new features, making logic changes to the backend or frontend, or deleting functional application files.

---

## SECTION B — TECH STACK

- **Git**: remote, add, commit, push.
- **PowerShell**: Command line environment to execute git operations.

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Configure Git Ignore
- **Objective**: Ensure that temporary development/testing artifacts are excluded.
- **Scope**: `.gitignore`
- **Output**: Updated `.gitignore` file.
- **Connects to**: Session 2.
- **Failure Surface**: Incorrect path syntax in `.gitignore` causing files to remain tracked.

### Session 2: Stage and Commit Pipeline Files
- **Objective**: Safely stage and commit code improvements, tests, and documentation.
- **Scope**: Git staging and commit operations.
- **Output**: A clean working directory with a new commit containing useful files.
- **Connects to**: Session 3.
- **Failure Surface**: Accidental inclusion of `.env` or sensitive databases (mitigated by checking `git status` before commit).

### Session 3: Push Commits to Target Repository
- **Objective**: Push all commits to the `dest` remote on the `main` branch.
- **Scope**: `git push`
- **Output**: Changes successfully pushed to `https://github.com/Shreyash-deve7/medical-ocr-pipeline.git`.
- **Connects to**: End of task.
- **Failure Surface**: Push rejected due to branch conflicts or permission issues.

---

## SECTION D — PROGRESS CHECKLIST

- [ ] Session 1: Configure Git Ignore
  - [ ] Add `frontend/playwright-report/` to `.gitignore`
  - [ ] Add `frontend/test-results/` to `.gitignore`
  - [ ] Add `frontend/ui-audit-screenshots/` to `.gitignore`
  - [ ] Add `result.json` to `.gitignore`
- [ ] Session 2: Stage and Commit Pipeline Files
  - [ ] Verify `git status` before committing
  - [ ] Stage all source code files, tests, scripts, and documentation
  - [ ] Commit staged files with a clear commit message
- [ ] Session 3: Push Commits to Target Repository
  - [ ] Dry-run push to verify access
  - [ ] Perform actual git push to `dest main`
