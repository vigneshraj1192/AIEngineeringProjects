---
name: feature_addition_skill
description: Workflow for adding new features adhering to existing codebase patterns and standards.
---

# Feature Addition Skill

## Objective
Implement new capabilities by inspecting existing repository architecture, designing clean interfaces, writing unit tests, and maintaining backward compatibility.

## Workflow
1. **explore_pattern**: Read similar existing feature implementations to follow conventions for style, error handling, and architecture.
2. **design**: Define the interface, function signatures, data models, and schemas before writing implementation code.
3. **implement**: Add the new functionality adhering to codebase patterns.
4. **test**: Write comprehensive unit and integration tests covering standard paths and error conditions.
5. **document**: Update docstrings, type annotations, and module documentation.

## Interface Design Checklist
- [ ] Match existing naming conventions (snake_case vs camelCase)
- [ ] Validate all new inputs and provide clear error messages
- [ ] Maintain full backward compatibility for existing callers
- [ ] Include clear docstrings with argument and return specifications
- [ ] Verify test suite passes without regressions

## Forbidden Actions
- Do not introduce breaking changes to existing public APIs unless explicitly requested.
- Do not add undocumented dependencies.
- Do not rewrite existing working subsystems.
