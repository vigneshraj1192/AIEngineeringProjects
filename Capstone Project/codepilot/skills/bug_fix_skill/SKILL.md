---
name: bug_fix_skill
description: Systematic workflow for reproducing, localizing, and fixing bugs with tests.
---

# Bug Fix Skill

## Objective
Reproduce the bug first with a failing test, localize the root cause in the codebase, apply a surgical fix, and verify resolution.

## Workflow
1. **reproduce**: Write a minimal failing test that triggers the exact bug reported in the issue. Run the test in the sandbox to observe the failure.
2. **localize**: Parse stack traces and pinpoint the file, function, and offending line number causing the defect.
3. **fix**: Implement the minimal, surgical code modification required to fix the root cause without side effects.
4. **verify**: Run the reproduction test and the existing test suite to ensure all tests pass cleanly.

## Debugging Checklist
- [ ] Reproduce failure before writing production code
- [ ] Check for None/null pointer dereferences or missing dict keys
- [ ] Validate type boundaries, off-by-one errors, and edge case arguments
- [ ] Ensure backward compatibility with existing callers
- [ ] Verify clean exit without leftover temp state

## Common Bug Patterns
- **Python**: `KeyError`, `AttributeError: 'NoneType'`, mutable default arguments `def f(x=[])`, unhandled exceptions.
- **JavaScript/TypeScript**: `TypeError: Cannot read properties of undefined`, unhandled Promise rejections, shallow copy mutations.

## Forbidden Actions
- Do not mark the task complete without a passing test in the sandbox.
- Do not perform broad refactoring outside the bug's scope.
- Do not suppress exceptions with empty `except:` or `catch(e) {}` blocks.
