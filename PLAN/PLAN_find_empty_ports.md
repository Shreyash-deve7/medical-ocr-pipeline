# PLAN - Find Empty Ports

## SECTION A — GOAL DEFINITION
1. **What is being built or changed?**
   We will create a utility script to find and list empty (available/free) unique TCP ports on the PC.
2. **What does "done" look like?**
   - A list of at least 20-30 available TCP ports is generated and presented to the user.
   - A reusable utility (either Python or PowerShell) is provided so the user can easily find free ports in the future.
3. **What is explicitly out of scope?**
   - Modifying system firewall or network rules.
   - Automatically assigning ports to services.

## SECTION B — TECH STACK
- **Language**: PowerShell (reusable script for Windows) / Python (cross-platform socket checking).
  - *Decision*: We will provide a simple PowerShell command and a reusable script because the user is running Windows and it runs natively in the terminal without virtual environment setups. We can also use standard Python socket library.
- **Commands/APIs**: PowerShell's `Get-NetTCPConnection` or Python `socket.bind` check.

## SECTION C — SESSION MODULARIZATION
### Session 1: Create Free Port Finder Utility
- **Objective**: Implement a script that tests a range of ports (e.g. 3000 to 9000) to see if they are currently in use.
- **Scope**: Create `scripts/find_free_ports.ps1` or similar.
- **Output**: A script file that scans ports and lists the free ones.
- **Connects to**: Session 2 (which runs the scan to list free ports).
- **Failure Surface**: The script fails if execution policy blocks PowerShell execution, or socket binding requires administrative privileges. We will design it to run without administrative rights.

### Session 2: Scan and Output Free Ports
- **Objective**: Run the script and extract a set of unique free ports, then display them to the user.
- **Scope**: Run command/execute script.
- **Output**: A clean markdown table of 20-30 available ports.
- **Failure Surface**: Network interface queries failing (unlikely).

## SECTION D — PROGRESS CHECKLIST
- [ ] Session 1: Create Free Port Finder Utility
  - [ ] Write a script to scan ports in `scripts/find_free_ports.ps1`
  - [ ] Verify script is syntax-error free
- [ ] Session 2: Scan and Output Free Ports
  - [ ] Execute script to list ports
  - [ ] Present the list of free ports to the user
