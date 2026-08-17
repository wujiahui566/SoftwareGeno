# Geno Implementation Roadmap

## Guiding approach

Build a deterministic vertical slice early, then add analytical depth. Each phase leaves the repository formatted, linted, type-checked, tested, and documented. A phase is complete only when its acceptance criteria are automated where practical.

## Phase 0 — Engineering foundation

**Depends on:** approved project specification and ADR 0001.

Deliverables:

- Python 3.12 `src`-layout package and CLI composition root.
- `pyproject.toml` with pinned development workflow for formatting, linting, static type checking, and testing.
- validated configuration model and canonical configuration snapshots.
- logging conventions, error taxonomy, and test directory/fixture skeleton.
- local MongoDB Docker Compose service and developer commands.

Acceptance criteria:

- A clean checkout can install dependencies and run one documented verification command.
- Formatting, lint, type checking, and an initial unit test suite pass.
- The CLI prints help/version and validates configuration without requiring MongoDB.
- No analysis or identity semantics are hidden in the CLI layer.

## Phase 1 — Domain model, identifier contract, and persistence skeleton

**Depends on:** Phase 0 and resolution of canonical serialization and domain model library decisions.

Deliverables:

- Typed domain models and enums for all concepts in `DATA_MODEL.md`.
- Identifier envelope and canonical serialization implementation with golden vectors.
- Persistence ports, MongoDB mappings, migrations, and required uniqueness indexes.
- PipelineRun, stage work-item, lease, and ProcessingFailure persistence.

Acceptance criteria:

- Identifiers are identical across repeated processes and tested platform-sensitive inputs.
- Domain logic has no imports from the MongoDB driver.
- MongoDB integration tests prove deterministic upserts and uniqueness constraints.
- A simulated interrupted stage can be reclaimed and finalized safely.
- Any GeneID contract change is mechanically visible through a scheme version.

## Phase 2 — Git acquisition, version selection, and file discovery

**Depends on:** Phase 1.

Deliverables:

- Repository registration and Git acquisition adapter.
- reference discovery, immutable commit resolution, version selection and ordering.
- isolated snapshot materialization and deterministic C/C++ file discovery.
- content hashing, generated-code classification hook, and related diagnostics.

Acceptance criteria:

- The fixture repository's selected tags/commits resolve to expected full SHAs and stable VersionIDs.
- Re-running acquisition/discovery creates no duplicate records.
- Paths are enumerated in stable order with tested exclusions and case behavior.
- A bad file or unavailable reference creates a diagnostic with the expected retry behavior.
- Analyzed repository code is never executed.

## Phase 3 — C/C++ parser adapter and candidate extraction

**Depends on:** Phase 2 and resolution of parser/toolchain decision.

Deliverables:

- language analyzer contracts and capability manifest.
- concrete C/C++ parser adapter with bounded execution.
- function/method extraction including spans, names, types, and parser diagnostics.
- C/C++ fixture covering free functions, methods, overloads, templates/macros as supported, and malformed input.

Acceptance criteria:

- Parser-specific node types do not cross the analyzer port.
- Candidate IDs and spans are stable across identical runs.
- Supported fixture candidates match reviewed golden output.
- Malformed input fails only its applicable file/function by default and fail-fast behavior is tested.
- Unsupported or ambiguous constructs emit explicit capability/diagnostic states.

## Phase 4 — Normalization, features, and filtering

**Depends on:** Phase 3 and resolution of normalization details, fuzzy hash, CFG, and metric definitions.

Deliverables:

- versioned C/C++ token/code normalizer.
- required feature extractors and per-feature provenance.
- explainable, versioned candidate filtering policies.
- artifact representation/retention implementation.

Acceptance criteria:

- Comment, irrelevant whitespace, function/parameter/local rename, and literal fixtures normalize exactly as specified.
- Golden tests freeze normalized bytes/tokens and feature values.
- Missing, unsupported, failed, and zero-valued features are distinguishable.
- Each generated feature records algorithm, version, configuration, timestamp, and inputs.
- Every rejection has deterministic reason codes/evidence and remains auditable.

## Phase 5 — Gene construction and occurrence deduplication

**Depends on:** Phase 4.

Deliverables:

- core identity envelope and GeneID construction.
- context identity and OccurrenceID construction.
- atomic/reconcilable gene-body and occurrence persistence.
- statistics projection and end-to-end `analyze`/`resume` CLI slice.

Acceptance criteria:

- Context-only renames/moves keep GeneID and create appropriate distinct occurrences.
- Identical normalized units across repositories share one SoftwareGene.
- Semantic fixture changes produce different GeneIDs under the frozen scheme.
- Repeated and interrupted analyses converge to identical database state.
- Gene bodies contain no repository/path/version fields except provenance references explicitly outside core identity.

## Phase 6 — Evolution analysis

**Depends on:** Phase 5 and resolution of version topology and similarity/matching policy.

Deliverables:

- deterministic consecutive-version comparison planning.
- exact and similarity candidate matching.
- classification and evidence for birth, retention, mutation, migration, split, merge, and disappearance.
- CLI command/status reporting for comparison jobs.

Acceptance criteria:

- Curated fixture histories exercise each relation type with reviewed expected edges.
- Split/merge edges preserve group semantics and stable ordering.
- Scores, thresholds, ambiguity, inputs, and algorithm/configuration versions are persisted.
- Re-running a comparison is idempotent; changing algorithm version creates a coexisting projection.
- Non-linear Git history behavior is documented and tested.

## Phase 7 — Gene families

**Depends on:** Phase 5; may proceed in parallel with Phase 6 once shared similarity primitives are stable.

Deliverables:

- versioned family-build job and deterministic clustering.
- family/member persistence, exact-family baseline, and similarity-family option.
- reproducible build manifest and status CLI.

Acceptance criteria:

- The same ordered input set and configuration yields identical memberships and family IDs.
- Exact duplicates cluster as expected; similarity fixtures meet declared thresholds.
- Multiple algorithm versions coexist without rewriting GeneIDs or prior families.
- Membership evidence and representative selection are auditable.

## Phase 8 — Incremental and operational hardening

**Depends on:** Phases 5–7.

Deliverables:

- new-version detection and dependency-aware artifact invalidation.
- robust retries, leases, reconciliation, resource bounds, and cleanup.
- structured metrics and run/failure inspection.
- performance profiling and an optional documented OpenSSL integration run.

Acceptance criteria:

- Adding one version processes only new or invalidated work and preserves previous IDs.
- Worker interruption and lease expiry recover without duplication or lost evidence.
- File/function failures allow unrelated work to finish; partial-success status is accurate.
- Measured CPU, memory, storage, and duration baselines are documented for the fixture and optional OpenSSL scope.
- Docker Compose and local workflows produce equivalent domain results.

## Phase 9 — Release readiness

**Depends on:** all earlier phases required for the chosen initial release scope.

Deliverables:

- user/operator documentation, schema migration/backup guidance, compatibility matrix, and release notes.
- end-to-end reproducibility suite and supported-version declaration.
- threat/resource review for parsing untrusted repositories.

Acceptance criteria:

- A clean machine can follow documentation to reproduce the fixture results.
- All quality gates and end-to-end tests pass in CI.
- Upgrade and rollback rehearsals protect immutable gene and occurrence evidence.
- Known limitations and all unresolved decisions affecting results are documented.

## Dependency summary

```text
Phase 0
  └── Phase 1
       └── Phase 2
            └── Phase 3
                 └── Phase 4
                      └── Phase 5
                           ├── Phase 6 ──┐
                           └── Phase 7 ──┴── Phase 8 ── Phase 9
```

## Unresolved technical decisions

These decisions should be resolved with focused prototypes and ADRs before their dependent phase:

Canonical serialization and GeneID core composition were resolved by ADR 0002 and are no longer open decisions.

1. **C/C++ parser**: libclang, tree-sitter, Clang tooling, or a hybrid; required fidelity for macros, templates, overloads, and compile commands.
2. **Compilation context**: whether and how to consume `compile_commands.json`, infer flags, and represent candidates that differ by preprocessor configuration.
3. **Normalization semantics**: precise handling of types, macros, preprocessor branches, member/field identifiers, labels, operators, string encodings, and literal categories.
4. **Source artifact storage**: MongoDB inline documents, GridFS, or content-addressed filesystem/object storage; retention and compression policy.
5. **Fuzzy/similarity method**: algorithm, licensing, deterministic implementation, thresholds, and scalable candidate index.
6. **AST and CFG schemas**: portable summaries, exception/short-circuit semantics, and behavior when a complete CFG is unavailable.
7. **Metric definitions**: exact LOC, cyclomatic, Halstead, and maintainability-index variants so values are comparable.
8. **Filtering policy**: initial thresholds and operational definition of trivial wrappers, insufficient information, generated code, and overly common public functions.
9. **Version ordering**: first-parent, topological, release-time, semantic-version, or configured ordering for branched histories and multiple tags.
10. **Evolution matching**: feature weighting, thresholds, tie-breaking, confidence/ambiguity, and split/merge inference.
11. **Family clustering**: connected components, hierarchical clustering, or another deterministic algorithm; snapshot scope and representative selection.
12. **MongoDB topology**: standalone simplicity versus replica-set transactions in local Docker Compose; reconciliation requirements remain either way.
13. **Model/config tooling**: concrete typed model, settings, MongoDB, CLI, lint, type-check, and test libraries and dependency-locking policy.
14. **Pipeline concurrency**: initial process model, lease duration/heartbeat, retry limits, and future queue boundary.
15. **Repository identity aliases**: preserving identity across URL moves, mirrors, forks, submodules, and Git SHA-1/SHA-256 repositories.
16. **Licensing/data policy**: permitted storage and redistribution of extracted source/normalized artifacts and repository attribution.

## Recommended first coding task

Implement **Phase 0 as a narrow engineering-foundation change**: create the Python 3.12 `src` layout, typed configuration skeleton, no-op Typer-style CLI (library choice to be confirmed), quality-tool configuration, a smoke test, and MongoDB Docker Compose service. Do not implement parsing or identity generation in that task.

The next task after the foundation should be a dedicated ADR/prototype that freezes canonical serialization and GeneID test vectors before persistence or analyzers can accidentally establish incompatible identity semantics.
