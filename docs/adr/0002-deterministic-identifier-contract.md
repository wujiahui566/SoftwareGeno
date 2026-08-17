# ADR 0002: Deterministic Identifier Contract Version 1

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** Geno project maintainers

## Context

ADR 0001 made deterministic domain identities and a core-only GeneID mandatory but deliberately deferred canonical serialization, Git/path normalization, and exact identity fields. Those details must be frozen before analyzers or persistence establish accidental compatibility contracts.

## Decision

Geno adopts identifier scheme version 1 as documented in `docs/DATA_MODEL.md` and implemented in `geno.identity`.

### Canonical serialization

Each identifier hashes an envelope with exactly three keys: `fields`, `kind`, and integer `scheme_version`. Before compact JSON serialization, all object keys and string values are Unicode NFC-normalized. Keys are sorted lexicographically; arrays retain order unless a field is explicitly a set, when the constructor deduplicates and sorts it. JSON is encoded as UTF-8 without ASCII escaping or insignificant whitespace.

The supported value subset is null, boolean, integer, string, array, and string-keyed object. Floating-point values are rejected to avoid cross-implementation numeric ambiguity. Normalized duplicate object keys are rejected. SHA-256 produces 64 lowercase hexadecimal characters appended to the kind's readable prefix.

### Location normalization

Network Git transports normalize to host, optional non-default port, owner/namespace, and repository name. Scheme and credentials do not participate. Hosts are IDNA-normalized and case-folded. Owner/name are NFC-normalized and case-folded, and one terminal `.git` is removed. The URL path must match the supplied normalized owner/name. Query strings, fragments, local/file URLs, and traversal are rejected.

Repository-relative paths are NFC-normalized and converted from Windows separators to POSIX separators. Empty/repeated separators and `.` segments are removed. Absolute paths, drive-qualified paths, empty results, and `..` traversal are rejected. Case is preserved.

### Exact participating fields

| Kind | Prefix | Fields |
|---|---|---|
| repository | `repo_` | host, optional non-default port, owner, name |
| version | `ver_` | repository ID, Git object format, full commit hash |
| source file | `file_` | version ID, normalized relative path |
| candidate unit | `unit_` | source-file ID, analyzer name/version, unit kind, start/end byte offsets |
| normalized unit | `norm_` | candidate-unit ID, normalization algorithm/version, configuration version |
| gene | `gene_` | language, normalization algorithm/version, normalized-core-code SHA-256 |
| occurrence | `occ_` | gene ID, candidate-unit ID |
| evolution edge | `edge_` | repository/from/to version IDs, relation, source/target occurrence sets, algorithm/version, configuration version |
| family | `fam_` | gene-member set, algorithm/version, configuration version |
| pipeline run | `run_` | repository/version scope, pipeline version, configuration ID, idempotency key |

### Gene identity boundary

The normalized core-code string supplied to GeneID construction is NFC-normalized and SHA-256 hashed. The identity layer performs no C/C++ normalization itself. Language and normalization contract identify how that core representation was produced.

No repository, version, commit, path, source span, original symbol/local name, calling context, timestamp, feature score, occurrence, family, evolution, pipeline-run, or database field participates in GeneID.

## Consequences

- Equivalent dictionary order, Unicode composition, supported Git transports, and Windows/POSIX relative paths converge deterministically where their contracts say they are equivalent.
- Mutable hosting metadata such as stars and descriptions cannot affect RepositoryID because it is absent from the constructor and envelope.
- Context changes affect occurrence/candidate identifiers but never GeneID.
- Renaming a local variable preserves GeneID only after the future normalizer maps both raw functions to identical canonical core code.
- Algorithm and identity behavior changes require new explicit versions and golden test vectors.
- Lowercasing owner/name follows the requested repository normalization contract. Hosts where path case is semantically distinct will need a future scheme version or host-specific policy rather than an in-place change.

## Compatibility and migration

This is the first implemented identifier contract. No persisted production identifiers exist, so no data migration is required. Scheme version 1 golden vectors are permanent regression fixtures. Any future incompatible change requires a new ADR, a new scheme version, coexistence rules, and an explicit migration plan; existing IDs must not be reinterpreted or rewritten silently.
