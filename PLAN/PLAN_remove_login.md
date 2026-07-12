# PLAN — Remove Login Screen

## SECTION A — GOAL DEFINITION

### 1. What is being built or changed?
We will remove the patient portal's login/registration screen in the frontend. Since the doctor portal does not have a login screen (it directly lists all patients from the open database), no changes are needed for the doctor side. For the patient portal, we will implement automatic authentication using a default patient account.

### 2. What does "done" look like?
- Opening the Patient Portal immediately shows the patient dashboard with the document uploader and list of reports, without displaying any login or registration form.
- The Patient Portal successfully retrieves and displays reports using an automatically generated or retrieved authentication token.
- The Doctor Portal continues to list patients and view their charts as before.

### 3. What is explicitly out of scope for this task?
Any changes to backend auth endpoints (`/api/patient/login`, `/api/patient/register`), database schemas, or doctor portal UI structure.

---

## SECTION B — TECH STACK

This task affects the frontend application:
- **Frontend**: React (TypeScript)
- **Files**:
  - [PatientPortal.tsx](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/frontend/src/pages/PatientPortal.tsx)

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Implement Auto-Login & Remove Auth Screen
- **Objective**: Replace the interactive login screen in `PatientPortal.tsx` with an automatic background login using a default patient credential (`5511999` / `password`).
- **Scope**: [PatientPortal.tsx](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/frontend/src/pages/PatientPortal.tsx)
- **Output**: Auto-login on mount, showing a loader during auth, and directly loading the Patient Dashboard.
- **Connects to**: Verification of patient report upload and viewing functionality.
- **Failure Surface**: Backend communication errors, default patient account missing (handled by automatically registering if login fails), or empty loading state.

---

## SECTION D — PROGRESS CHECKLIST

- [x] Session 1: Implement Auto-Login & Remove Auth Screen
  - [x] Modify [PatientPortal.tsx](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/frontend/src/pages/PatientPortal.tsx) to automatically authenticate a default patient (`5511999` / `password`) on mount.
  - [x] Remove the interactive login/register form UI from [PatientPortal.tsx](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/frontend/src/pages/PatientPortal.tsx).
  - [x] Add a loader state during auto-login.
  - [x] Verify that opening Patient Portal bypasses login and displays reports correctly.
