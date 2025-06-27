# Rules for Generation of a Task List from a PRD (Python Edition)

## Goal

To guide an AI assistant in creating a detailed, step-by-step task list in Markdown format based on an existing Product Requirements Document (PRD). The task list should guide a developer through implementation in a Python codebase.

## Output

- **Format:** Markdown (`.md`)
- **Location:** `/tasks/`
- **Filename:** `tasks-[prd-file-name].md`  
  (e.g., `tasks-prd-user-profile-editing.md`)

## Process

1. **Receive PRD Reference:** The user points the AI to a specific PRD file.  
2. **Analyze PRD:** The AI reads and analyzes the functional requirements, user stories, and other sections of the specified PRD.  
3. **Phase 1: Generate Parent Tasks:**  
   - Create the `/tasks/tasks-[prd-file-name].md` file.  
   - Generate ~5 high-level “parent” tasks required to implement the feature.  
   - Present these parent tasks in the specified format (no sub-tasks yet).  
   - Prompt the user:  
     > “I have generated the high-level tasks based on the PRD. Ready to generate the sub-tasks? Respond with ‘Go’ to proceed.”  
4. **Wait for Confirmation:** Pause until the user replies “Go.”  
5. **Phase 2: Generate Sub-Tasks:**  
   - Break down each parent task into actionable sub-tasks.  
   - Ensure sub-tasks cover implementation details implied by the PRD.  
6. **Identify Relevant Files:**  
   - List the Python modules and test files that will be created or modified.  
   - Include brief descriptions for each.  
7. **Generate Final Output:**  
   - Combine the parent tasks, sub-tasks, relevant files, and any notes into the final Markdown.  
8. **Save Task List:**  
   - File path: `/tasks/tasks-[prd-file-name].md`  
   - Ensure the base name matches the input PRD file.

## Output Format


## Relevant Files

- `app/feature_x.py` – Main module implementing Feature X.
- `app/feature_x_service.py` – Business-logic layer for Feature X.
- `tests/test_feature_x.py` – Unit tests for `feature_x.py` and service logic.
- `app/utils/helpers.py` – Utility functions needed for Feature X.
- `tests/test_helpers.py` – Unit tests for helper functions.

### Notes

- Place test files alongside the modules they cover, prefixed with `test_`.
- Run tests with `pytest [optional/path/to/test_file.py]`. Omit the path to run the full suite.

## Tasks

- [ ] 1.0 Parent Task Title
  - [ ] 1.1 [Sub-task description 1.1]
  - [ ] 1.2 [Sub-task description 1.2]
- [ ] 2.0 Parent Task Title
  - [ ] 2.1 [Sub-task description 2.1]
- [ ] 3.0 Parent Task Title (may not require sub-tasks if purely structural or configuration)
