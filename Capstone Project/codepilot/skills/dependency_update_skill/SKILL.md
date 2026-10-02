---
name: dependency_update_skill
description: Workflow for upgrading packages, managing lockfiles, and verifying breaking changes.
---

# Dependency Update Skill

## Objective
Safely upgrade external packages, resolve version constraints, update dependency manifests/lockfiles, and verify full test suite integrity.

## Workflow
1. **check_changelog**: Review upstream changelogs, release notes, and migration guides between versions to spot breaking changes and deprecated APIs.
2. **update**: Modify requirement/package configuration files (`pyproject.toml`, `requirements.txt`, `package.json`).
3. **resolve_conflicts**: Fix any API drift, deprecated calls, or peer dependency incompatibilities.
4. **test_all**: Execute the entire automated test suite to confirm complete compatibility.

## Breaking Change Patterns by Ecosystem
- **Python (pip/uv/poetry)**: Deprecated module relocations, Pydantic v1 -> v2 schema shifts, synchronous to async transitions.
- **Node.js (npm/yarn/pnpm)**: CommonJS to ESM transition (`require` vs `import`), node engine version bumps.
- **Rust (cargo)**: Trait method additions without default implementations, edition changes.

## Forbidden Actions
- Do not blindly bump major versions without inspecting the changelog.
- Do not delete tests that fail after dependency upgrades; fix the calling code instead.
- Do not bypass dependency hash or lockfile verification.
