# PyCharm Inspections CLI — Workflow Friction Solutions

## Problem

PyCharm's command-line inspector requires the IDE to be closed and can collide
with the IDE's normal lock files.

## Solutions (Ranked)

### 1. Dedicated CLI profile (Recommended)

- Run the installed PyCharm executable directly with a separate profile selector
- The main IDE configuration remains untouched
- The wrapper still scans the entire project

### 2. Docker/Container

- Ephemeral inspection instance, zero host impact
- More setup overhead, slower startup
- Better for reproducibility/CI

### 3. File Watcher (No code needed)

- PyCharm's built-in auto-inspect on file changes, writes to the result file
- Script reads output, zero friction
- Good if you do not need real-time results

### 4. IDE Plugin

- Expose the inspection engine through a socket or an API
- This option is complex, but it provides the most elegant design for long-term use

### 5. Headless Instance

- A separate PyCharm process with its own lock files
- A useful fallback, but it requires careful configuration isolation

## Current State

- `scripts/run_pycharm_inspection.ps1` runs the installed PyCharm executable directly
- It uses the project inspection profile and full-project scope
- The runner masks the generated `mutants/` tree inside the inspection
  container, so duplicate mutation-test copies do not pollute project-wide
  duplicate-code results.
- The latest run completed with zero findings.
