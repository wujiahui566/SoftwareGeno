# Geno Project Specification

## 1. Problem definition

Open-source software changes continuously, and code units are frequently copied, renamed, moved, refactored, split, or merged. Repository paths, symbols, and version labels therefore cannot provide a stable identity for the underlying code.

Geno is a foundational software-analysis platform that extracts function-level "software genes" from historical versions of Git repositories. It assigns identities based on normalized code properties, stores the code-derived gene body independently from each observed occurrence, and provides the evidence needed to trace genes within and across repositories over time.

The initial product is a deterministic, restartable command-line batch pipeline for C and C++ source code, backed by MongoDB and runnable locally or with Docker Compose.

## 2. Terminology

- **Repository**: A registered Git repository and its acquisition metadata.
- **Version**: A selected immutable repository snapshot, normally identified by a resolved commit SHA. A tag or release is a label for a snapshot, not its identity.
- **Source file**: A supported file discovered in one materialized version.
- **Candidate unit**: A parser-extracted C or C++ function or method before normalization and filtering.
- **Normalized unit**: A canonical representation of a candidate after comments and irrelevant whitespace are removed, identifiers are normalized by role, and literals are replaced with typed placeholders.
- **Core identity**: Versioned, code-derived identity material that excludes repository, version, path, location, and original symbol names.
- **Context identity**: Deterministic identity material describing one gene occurrence, including its repository snapshot and source location.
- **GeneID**: The stable identifier derived only from the canonical core identity envelope.
- **Software gene / gene body**: The deduplicated record for one GeneID, containing canonical core identity and reusable features.
- **Gene occurrence**: Evidence that a gene body appeared at a particular location in a particular repository version.
- **Feature**: A computed measurement or representation accompanied by algorithm, algorithm version, configuration version, and creation time.
- **Evolution edge**: A version-to-version relation between occurrences or genes, such as birth, retention, mutation, migration, split, merge, or disappearance.
- **Gene family**: A versioned grouping of exact or similar genes produced by a specified family-building algorithm.
- **Pipeline run**: A durable record of requested work, configuration, stage progress, counters, and outcome.
- **Processing failure**: A structured diagnostic for a failed repository, version, file, function, or pipeline stage.
- **Idempotent**: Repeating the same operation with the same inputs and configuration produces the same domain records and does not create duplicates.

## 3. Scope

### 3.1 Initial implementation

- Python 3.12 implementation.
- MongoDB persistence.
- Local Git repository acquisition and historical snapshot materialization.
- Tag, release-label, commit, and configured snapshot discovery and selection.
- C and C++ source-file discovery.
- Function and method extraction through a parser abstraction.
- Deterministic normalization of function code.
- Extraction of normalized code and token digests, fuzzy hash, AST and CFG summaries, call set, LOC, cyclomatic complexity, Halstead metrics, and maintainability index.
- Configurable filtering of ineffective candidates.
- Stable core and context identity generation.
- Separate persistence and deduplication of gene bodies and occurrences.
- Consecutive-version evolution analysis.
- Exact and similarity-based family construction.
- Incremental analysis of newly discovered repository versions.
- CLI operation on a local machine and through Docker Compose.
- A small C/C++ fixture; an OpenSSL example may be supplied as an optional integration exercise.

### 3.2 Future-compatible scope

The architecture must permit additional analyzers for Java, Python, Go, JavaScript/TypeScript, ArkTS, and other languages without coupling their parsers or normalization rules to the C/C++ implementation.

## 4. Non-goals

The initial version does not include:

- vulnerability or CVE detection;
- security-risk scoring or malicious-code detection;
- binary analysis;
- package-manager analysis;
- a graphical frontend or public web API;
- user or access management;
- distributed-cluster execution;
- deep-learning model training;
- LLM-based code analysis;
- support for source languages other than C and C++.

Evolution labels and similarity scores describe code history only and must not be presented as security findings.

## 5. Functional requirements

### FR-1 Repository registration and acquisition

The system shall register a Git repository using a deterministic RepositoryID, retain its canonical source locator, fetch or update it safely, and record acquisition diagnostics. Credentials and secrets shall not be persisted in repository records or logs.

### FR-2 Version discovery and selection

The system shall discover available references, resolve selected references to immutable commit SHAs, preserve aliases such as tags, and deterministically order selected versions. Re-running discovery shall update metadata without duplicating versions.

### FR-3 Snapshot materialization

The system shall materialize selected commits into isolated work areas, verify the resolved commit, and make interrupted materialization safe to retry.

### FR-4 Source discovery

The system shall identify supported C/C++ files using versioned configuration, stable ordering, explicit inclusion/exclusion rules, and generated-code heuristics. Each file shall have a deterministic identity and content digest.

### FR-5 Parsing and candidate extraction

The system shall invoke a C/C++ analyzer through a language-neutral interface and extract functions and methods with source spans, symbol/type context, parser diagnostics, and raw-content references. A file failure shall not terminate unrelated files unless fail-fast is enabled.

### FR-6 Normalization

The system shall deterministically canonicalize each candidate by removing comments and irrelevant whitespace, normalizing function, parameter, and local-variable names, and replacing literals with typed placeholders. The normalization algorithm and version shall be explicit inputs to identity generation.

### FR-7 Feature extraction

The system shall compute the required code, token, fuzzy, structural, call, size, and complexity features. Every feature value shall record its algorithm name, algorithm version, creation time, and relevant configuration version.

### FR-8 Filtering

The system shall apply versioned, explainable rules for short or low-information functions, trivial wrappers, generated code, and overly common public functions. A rejection shall preserve its reason and must not erase the candidate evidence needed to audit it.

### FR-9 Identity generation

The system shall derive GeneID exclusively from a canonical, versioned core identity envelope. It shall derive occurrence/context identifiers separately from immutable repository, version, file, and source-location information. Identity generation shall be deterministic across machines.

### FR-10 Persistence and deduplication

The system shall upsert one gene body per GeneID and separately store occurrences. It shall deduplicate within a version, across versions, and across repositories without relying on MongoDB ObjectId as a domain identifier.

### FR-11 Evolution analysis

The system shall compare deterministically ordered consecutive versions and persist evidence-scored birth, retention, mutation, migration, split, merge, and disappearance relations. Algorithms and thresholds shall be versioned.

### FR-12 Gene-family construction

The system shall build reproducible exact or similar gene families, retaining the family algorithm, parameters, membership score, and evidence. Rebuilding under a new algorithm version shall not silently rewrite old results.

### FR-13 Incremental processing

The system shall detect newly selected commits, reuse completed compatible artifacts, and process only missing or invalidated stages. Changed algorithm or configuration versions shall invalidate only dependent artifacts.

### FR-14 CLI and operations

The CLI shall support repository registration, version discovery/selection, analysis, resume, status inspection, and family/evolution jobs. Commands shall return meaningful exit codes and support human-readable and machine-readable output.

### FR-15 Diagnostics and observability

Every failed file or function shall create a structured ProcessingFailure. Runs shall expose stage status, counters, durations, configuration identity, and sufficient correlation identifiers for diagnosis. Fail-fast behavior shall be configurable and off by default.

## 6. Non-functional requirements

- **Determinism**: Stable ordering, canonical serialization, fixed encodings, explicit tool versions, and no dependence on wall-clock time in domain identifiers.
- **Idempotency**: All durable writes use deterministic keys and upsert semantics; retries do not multiply records.
- **Restartability**: Durable stage checkpoints and leases allow a stopped run to resume without corrupting completed results.
- **Incrementality**: Artifact provenance identifies when prior work is compatible and reusable.
- **Modularity**: Domain logic is independent of CLI, Git, parser processes, and MongoDB drivers.
- **Typing**: Public Python interfaces and domain models are statically typed and pass the configured type checker.
- **Testability**: External systems are accessed through ports; deterministic fixture and integration tests cover identity and retry behavior.
- **Fault isolation**: File/function failures are recorded and processing continues unless fail-fast is explicitly requested.
- **Batch suitability**: Work is bounded, pageable, observable, and free of assumptions about interactive execution.
- **Horizontal-scaling readiness**: Work items have stable keys, claim/lease semantics, and atomic state transitions even though the first deployment is local.
- **Compatibility**: Stored schemas and algorithms carry versions; migrations are explicit and reversible where practical.
- **Reproducibility**: A result can be traced to source commit, content digest, configuration version, and algorithm/tool versions.
- **Performance baseline**: The small fixture completes locally without manual intervention; larger performance targets shall be established from measured OpenSSL runs.
- **Security hygiene**: Treat repositories as untrusted input, bound parser resources, avoid executing analyzed code, and redact credentials from records and diagnostics.

## 7. Success criteria

The first implementation is successful when:

1. A clean environment can start MongoDB and run Geno through documented local and Docker Compose workflows.
2. The C/C++ fixture is analyzed end to end and produces candidates, normalized units, features, gene bodies, and separate occurrences.
3. Re-running the same analysis produces no duplicate domain records and identical identifiers and code-derived values.
4. Identical normalized functions in different files, versions, or repositories share a GeneID while retaining distinct occurrences.
5. Renaming only context-level properties does not change GeneID; a core-semantic change can produce a different GeneID and a versioned mutation relation.
6. Consecutive fixture versions demonstrate and test the supported evolution relation types with retained evidence.
7. A deliberately malformed file and function create diagnostics while other files complete; fail-fast mode stops as configured.
8. An interrupted run resumes from durable state, and adding a new repository version reuses compatible prior results.
9. Every persisted feature and analysis relation includes provenance and configuration/algorithm versions.
10. Formatting, linting, static type checking, unit tests, and integration tests pass in the supported development workflow.
