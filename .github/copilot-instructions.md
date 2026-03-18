STRICT PROJECT RULES

- One bug = one file or one module only
- Never modify multiple layers (frontend/backend/db) in one task
- Do not guess database schema
- Do not add fallback logic based on runtime errors
- Always find root cause before fixing
- Always explain before changing code
- Always provide exact diff

DATABASE:
- Do not assume column names
- Only use confirmed schema from code
- If schema is unknown — STOP and report

BACKEND:
- Only modify specified router/file
- Do not touch unrelated endpoints

FRONTEND:
- Never modify UI to hide backend errors

FORBIDDEN:
- fallback hacks
- broad refactoring
- guessing logic
