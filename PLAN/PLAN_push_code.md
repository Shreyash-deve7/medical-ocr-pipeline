# PLAN — Push Code to Repository

## SECTION A — GOAL DEFINITION

### 1. What is being built or changed?
No feature changes are being made. The task is to configure the Git repository to point to the new remote URL (`https://github.com/Shreyash-deve7/medical-ocr-pipeline`), update `.gitignore` to ensure all sensitive or private patient data files (PHI) and local secrets are excluded, and push only safe project files to the repository.

### 2. What does "done" look like?
- `.gitignore` is updated to explicitly ignore `Patient_Kastoor/` and `WhatsApp Unknown 2026-04-27 at 12.10.10/`.
- Local sensitive files (`.env`, `*.db`, API keys) are verified to be excluded.
- The new Git remote is configured.
- Code is pushed to `https://github.com/Shreyash-deve7/medical-ocr-pipeline` on the appropriate branch.

### 3. What is explicitly out of scope for this task?
Modifying application code, changing backend/frontend logic, or editing features.

---

## SECTION B — TECH STACK

This task involves:
- **Git**: Config, staging, committing, and pushing.
- **Tools**: PowerShell to run commands.

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Clean and Prepare
- **Objective**: Ensure sensitive files are ignored.
- **Scope**: `.gitignore`, `.env`, patient data directories.
- **Output**: Updated `.gitignore` file, verified clean git status.
- **Connects to**: Session 2.
- **Failure Surface**: Accidentally staging a sensitive folder/file.

### Session 2: Remote Configuration and Push
- **Objective**: Add remote and push codebase.
- **Scope**: Git remote, git push.
- **Output**: Codebase pushed to `https://github.com/Shreyash-deve7/medical-ocr-pipeline`.
- **Connects to**: End of task.
- **Failure Surface**: Authentication failure, remote branch conflicts.

---

## SECTION D — PROGRESS CHECKLIST

- [ ] Session 1: Clean and Prepare
  - [ ] Add `Patient_Kastoor/` and `WhatsApp Unknown 2026-04-27 at 12.10.10/` to `.gitignore`
  - [ ] Verify that no sensitive files or folders are staged or tracked using `git status`
- [ ] Session 2: Remote Configuration and Push
  - [ ] Add new remote `https://github.com/Shreyash-deve7/medical-ocr-pipeline` (e.g. as remote `dest` or change `origin`)
  - [ ] Stage and commit changes (safe files only)
  - [ ] Push code to the new remote repository
