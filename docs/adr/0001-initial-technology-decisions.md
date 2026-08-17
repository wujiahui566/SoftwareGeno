# ADR 0001: Initial Technology and Domain Boundaries

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** Geno project maintainers

## Context

Geno needs an initial technical boundary that supports deterministic extraction of function-level software genes from repository history without prematurely coupling the platform to one parser, source language, or storage representation. The core distinction is between code-derived identity and the context in which code occurs.

The first release is a local/batch foundation rather than a distributed or user-facing product. Its choices should enable a testable vertical slice while retaining clear extension points.

## Decisions

### Python 3.12

The application will be implemented in Python 3.12. Public interfaces and domain models will be typed, and formatting, linting, static type checking, and tests are mandatory quality gates.

### MongoDB

MongoDB will store repository/version metadata, analysis evidence, gene bodies, occurrences, evolution relations, families, runs, and failures. Domain identifiers are deterministic and must not depend on MongoDB ObjectId. Collections and documents use explicit schema versions and versioned migrations.

### Function-level C/C++ first

The initial supported source languages are C and C++. The analysis unit is a function or method. Other languages remain future extension work and must not complicate the first implementation with unused behavior.

### Parser hidden behind an interface

The concrete C/C++ parser is an infrastructure adapter behind a language-neutral analyzer interface. Parser-specific nodes, handles, and diagnostics are translated at the boundary and do not enter domain or orchestration APIs. The concrete parser remains a separately recorded technical decision after prototyping.

### Gene body separated from occurrence

A SoftwareGene stores deduplicated core-derived body/identity information. A GeneOccurrence records each repository/version/file/location observation and points to the SoftwareGene. The system never copies a full gene body into every occurrence as its authoritative representation.

### Core identity separated from context identity

GeneID is derived only from a canonical, versioned core identity envelope. Repository, version, commit, file path, original function name, source location, timestamps, and calling context are context fields and do not affect GeneID. Core/context semantics may change only through an explicit ADR, version change, compatibility plan, and regression vectors.

## Consequences

### Positive

- Python offers a productive typed ecosystem for CLI, Git/process orchestration, testing, and MongoDB integration.
- MongoDB accommodates heterogeneous provenance-bearing analysis documents and atomic deterministic upserts.
- C/C++ scope allows parser and normalization semantics to be made rigorous before adding languages.
- A parser port permits evaluation or replacement of parser technology without changing the domain pipeline.
- Separating gene bodies from occurrences enables exact deduplication within versions, across versions, and across repositories.
- Separating core from context allows code identity to survive moves and context-only renames.

### Costs and constraints

- Python adapters may need native parser libraries or subprocesses and careful resource management for large repositories.
- MongoDB relationships and referential integrity must be enforced by application invariants, indexes, reconciliation, and tests.
- Parser-neutral contracts may expose capability gaps; unsupported data must be explicit rather than fabricated.
- Identity and normalization contracts become long-lived compatibility surfaces. Changing them requires coexistence or migration rather than in-place reinterpretation.
- Local execution is the only initial deployment target, but work records and identifiers must remain suitable for later horizontal scaling.

## Alternatives considered

- **Relational database:** Strong relational constraints were attractive, but MongoDB was selected by project definition and suits varied analysis/provenance payloads. Explicit indexes and application integrity checks are required.
- **Parser-specific domain model:** Rejected because it would impede alternative parsers and future languages.
- **Occurrence-specific gene records:** Rejected because it duplicates gene bodies and makes cross-context identity secondary.
- **Path/name-based GeneID:** Rejected because moves, renames, versions, and forks would change code identity.
- **Multiple languages immediately:** Rejected to keep normalization and identity semantics testable in the initial vertical slice.

## Follow-up decisions required

Separate ADRs or approved design records must select the C/C++ parser, freeze canonical serialization and GeneID composition, define normalization rules, choose artifact storage, define version ordering, and specify evolution/family similarity algorithms before those components are implemented.
