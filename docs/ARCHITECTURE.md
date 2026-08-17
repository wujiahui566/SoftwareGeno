# Geno Architecture

## 1. Architectural style

Geno uses a ports-and-adapters architecture around a typed domain and application core. Domain models and deterministic analysis logic do not import MongoDB, Git-process, parser-process, CLI, or container concerns. Infrastructure adapters implement explicit ports and are composed at the CLI boundary.

The initial executable is a single Python batch application. Its work model nevertheless uses deterministic work keys, stage checkpoints, and claim/lease semantics so stages can later be run by multiple workers without redesigning domain identity.

## 2. Component architecture

```text
CLI / composition root
        |
        v
Pipeline orchestrator -----> observability / run journal
        |
        +---- application use cases and stage services
        |          |
        |          v
        |      domain models, policies, identity rules
        |          ^
        |          |
        +----------+-------------------------------+
                   | ports                         |
          +--------+---------+----------+-----------+---------+
          v                  v          v                     v
     Git adapter      language analyzer MongoDB adapter  local workspace
                            |
                            v
                     C/C++ parser adapter
```

## 3. Module responsibilities

A proposed Python package layout is shown in the repository structure at the end of this document.

### `configuration`

Loads validated settings; produces canonical configuration snapshots and ConfigurationIDs; supplies filter thresholds, discovery rules, algorithm selections, resource limits, and fail-fast policy. Secrets remain outside canonical persisted configuration.

### `domain`

Defines immutable/value-oriented domain models, enums, invariants, lifecycle states, deterministic identifier value types, and pure policies. It must not depend on infrastructure modules.

### `acquisition`

Defines repository acquisition ports and Git subprocess adapters. It canonicalizes credential-free
source locators, registers repositories, maintains deterministic bare mirrors, fetches objects, and
reads references and commit metadata without executing repository code.

### `versions`

Discovers references, selects snapshots according to configuration, resolves aliases to commit SHAs, and determines a stable chronological/topological comparison order. Ambiguous histories are represented explicitly.

### `discovery`

Walks a materialized snapshot in stable path order, applies include/exclude and generated-code rules, classifies supported languages, hashes content, and emits SourceFileRecords.

### `analyzers`

Owns the language-neutral `LanguageAnalyzer` port and registry. An analyzer reports its language, capabilities, parser/tool versions, supported extensions, candidate units, and diagnostics.

### `analyzers.cpp`

Adapts the chosen C/C++ parsing technology. It translates parser-specific nodes and errors into parser-independent candidates, source spans, type/call information, AST summaries, and CFG inputs. No parser-specific object crosses the adapter boundary.

### `normalization`

Transforms candidates into canonical token/code representations using language-specific, versioned normalization strategies. It produces both canonical bytes for hashing and auditable normalized representations.

### `features`

Runs versioned feature extractors and emits provenance-bearing feature values. Extractors declare dependencies, allowing selective recomputation.

### `filtering`

Evaluates versioned deterministic rules and produces an accept/reject decision with reason codes and evidence. It never deletes candidates.

### `identity`

Canonicalizes identity envelopes and computes GeneID, occurrence and other domain identifiers. Changes to this module require an ADR and migration/compatibility plan.

### `persistence`

Defines repository/unit-of-work ports and MongoDB adapters. It owns collection mappings, atomic upserts, indexes, leases, schema migration execution, and serialization without leaking driver types into the domain.

### `deduplication`

Coordinates idempotent gene-body and occurrence upserts and updates derived statistics. Exact GeneID deduplication precedes any similarity comparison.

### `evolution`

Matches occurrences between consecutive selected versions, classifies lifecycle relations, retains scores/evidence, and emits versioned EvolutionEdges. Matching and classification are separate policies.

### `families`

Builds reproducible family snapshots from exact and similarity relations. It preserves algorithm version and parameters and stores membership independently from gene bodies.

### `pipeline`

Defines stage contracts and their dependency graph, creates resumable work items, claims work with leases, records progress, applies retry/fail-fast policy, and invalidates artifacts whose provenance is incompatible.

### `cli`

Parses commands, validates user input, invokes application use cases, renders text or structured results, and maps outcomes to exit codes. It contains no analysis policy.

### `observability`

Provides structured logging, timing, counters, correlation context, and diagnostic construction. Logs are operational output; ProcessingFailures are durable domain records.

### `migrations`

Tracks storage schema, canonical serialization, identity, algorithm, and compatibility versions. Migrations never silently reinterpret existing identities.

## 4. Dependency direction

Dependencies point inward:

```text
domain <- application/stages <- CLI
   ^             ^              |
   |             |              v
   +------ ports +--------- infrastructure adapters
```

Rules:

1. `domain` imports only the Python standard library and deliberately selected type/model primitives.
2. Application services depend on domain types and abstract ports.
3. Infrastructure adapters depend on ports and domain serialization contracts.
4. CLI and the composition root choose concrete adapters; inner modules never choose them.
5. Language-neutral orchestration never imports a concrete C/C++ parser.
6. Evolution and family analysis consume stored domain projections rather than parser objects.
7. MongoDB `_id` may mirror a deterministic domain ID for convenience, but no domain rule may derive from ObjectId.

## 5. Complete processing sequence

Each stage receives a PipelineRunID, ConfigurationID, immutable input identifiers, and a stage-attempt context. Outputs are written before the stage checkpoint is atomically marked complete.

1. **Load configuration**: Validate settings, resolve enabled algorithms, redact secrets, canonicalize the effective configuration, and compute ConfigurationID.
2. **Create or resume run**: Compute a deterministic work scope and idempotency key, create the PipelineRun, or resume the run already identified by that request. A caller must supply a new stable key to request a separate execution of the same scope.
3. **Register repository**: Canonicalize the Git locator, compute RepositoryID, and upsert repository metadata.
4. **Acquire repository**: Clone/fetch into a managed object cache, record the observed remote state, and isolate failures.
5. **Discover references**: Enumerate tags and configured commit/release references and resolve each to a commit SHA.
6. **Select versions**: Apply selection policy, upsert VersionRecords, and establish deterministic comparison ordering with recorded rationale.
7. **Materialize snapshot**: Produce a read-only worktree/archive for a selected commit and verify its content source.
8. **Discover files**: Traverse in canonical path order, classify supported C/C++ files, hash bytes, and upsert SourceFileRecords.
9. **Parse file**: Select an analyzer by detected language, enforce parser resource bounds, and emit CandidateUnits plus diagnostics.
10. **Normalize candidate**: Apply a declared normalization version and persist a NormalizedUnit. A normalization failure affects only that candidate by default.
11. **Extract features**: Execute the dependency-ordered feature extractors and persist provenance-bearing GeneFeatures.
12. **Filter candidate**: Apply rules in stable order and persist the decision, reasons, and evidence. Rejected candidates do not proceed to gene construction.
13. **Construct core identity**: Build the canonical core envelope from approved core components and their semantic versions; serialize it canonically and compute GeneID.
14. **Construct context identity**: Build repository/version/file/span and contextual attributes; compute OccurrenceID separately.
15. **Persist and deduplicate**: Atomically upsert the SoftwareGene by GeneID, then the GeneOccurrence by OccurrenceID. Link reusable artifacts by deterministic ID.
16. **Update statistics**: Recompute or increment versioned materialized statistics idempotently from occurrence evidence.
17. **Analyze evolution**: Once required versions are complete, compare each selected consecutive pair, perform exact then similarity matching, and persist typed edges and unmatched birth/disappearance evidence.
18. **Build families**: Run a versioned family algorithm over eligible genes and similarities and persist a family snapshot and memberships.
19. **Finalize run**: Aggregate counters and diagnostics and set `succeeded`, `partially_succeeded`, or `failed`. Cleanup of materialized workspaces is best-effort and does not erase analysis records.

On retry, a stage first checks for an output with the same deterministic input identity and compatible provenance. It reuses a complete output, repairs an incomplete write through upsert, or recomputes only when compatibility rules require it.

## 6. Identity and compatibility boundary

Core normalization and identity semantics form a compatibility boundary. The GeneID input is a canonical envelope containing at least:

- an identity-scheme name and version;
- source-language identity;
- normalization algorithm name/version;
- the selected normalized representation digest(s);
- any structural feature explicitly declared identity-bearing.

Repository, commit, version label, path, original function name, raw location, timestamps, and similarity/fuzzy features are not core identity inputs. A change to identity-bearing fields, canonical serialization, or normalization semantics creates a new identity-scheme version and requires an ADR plus an explicit migration or coexistence strategy.

## 7. Extension points for new languages

New language support is added by registering implementations of narrow interfaces:

- `LanguageDetector`: recognizes files using content/path evidence.
- `LanguageAnalyzer`: returns language-neutral candidates and diagnostics.
- `Normalizer`: applies language-specific identifier, token, and literal rules.
- `StructuralFeatureProvider`: supplies AST/CFG summaries where supported.
- `ComplexityProvider`: supplies metrics with defined language semantics.
- `CallExtractor`: supplies normalized calls with confidence and resolution kind.
- `FilterPolicy`: adds language-specific ineffective-unit rules.

Every implementation declares a capability manifest and algorithm versions. The pipeline requests capabilities rather than assuming all analyzers can provide identical structure. Missing optional capabilities are recorded explicitly, not encoded as zero values. Cross-language families are disabled initially; a future algorithm may enable them only with its own feature contract and version.

Adding a language should require a new adapter package, fixture corpus, configuration registration, and contract tests—not modifications to repository acquisition, persistence semantics, orchestration, or the CLI command model.

## 8. Proposed repository structure

```text
SoftwareGeno/
├── CODEX.md
├── LICENSE
├── README.md
├── pyproject.toml
├── compose.yaml
├── configs/
│   └── default.toml
├── docs/
│   ├── PROJECT_SPEC.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── ROADMAP.md
│   └── adr/
│       └── 0001-initial-technology-decisions.md
├── src/
│   └── geno/
│       ├── cli/
│       ├── configuration/
│       ├── domain/
│       ├── repositories/
│       ├── versions/
│       ├── discovery/
│       ├── analyzers/
│       │   └── cpp/
│       ├── normalization/
│       ├── features/
│       ├── filtering/
│       ├── identity/
│       ├── persistence/
│       │   └── mongodb/
│       ├── deduplication/
│       ├── evolution/
│       ├── families/
│       ├── pipeline/
│       ├── observability/
│       └── migrations/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   └── fixtures/
│       └── cpp/
├── scripts/
└── docker/
```

Only the documentation files and `LICENSE` exist at the end of the specification task. The remaining entries are the proposed implementation layout, not files to create now.
