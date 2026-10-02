---
name: documentation_skill
description: Workflow for updating user guides, API references, docstrings, and README docs.
---

# Documentation Skill

## Objective
Author and update documentation to mirror implementation changes, ensuring technical accuracy, coherent style, and working code samples.

## Workflow
1. **read_existing**: Read existing docs and README files to match voice, tone, formatting standards, and diagram conventions.
2. **draft**: Write concise, accurate explanations with runnable code examples.
3. **review_accuracy**: Verify that documented flags, parameters, and return types match the actual code definitions.
4. **update_index**: Ensure navigation links, table of contents, and references are updated.

## Documentation Checklist
- [ ] Match existing Markdown formatting style (headers, badges, code blocks)
- [ ] Ensure all code snippets in examples are syntactically valid and runnable
- [ ] Update README / user guide if public CLI or API behavior changes
- [ ] Verify relative links and image references resolve properly

## Forbidden Actions
- Do not add hypothetical or unverified features to documentation.
- Do not leave placeholder text (e.g., "TODO: explain this").
- Do not modify code logic when only documentation was requested.
