# Geno Data Model

## 1. Modeling principles

- Gene bodies are immutable, core-derived records shared by all occurrences.
- Context and location belong to occurrences, not gene bodies.
- Every domain object has a deterministic string identifier independent of MongoDB ObjectId.
- Raw evidence, derived artifacts, and materialized statistics are distinct lifecycles.
- Derived values carry algorithm/configuration provenance and may coexist across versions.
- Immutable source commits and content digests anchor reproducibility.
- MongoDB documents use explicit `schema_version` fields and UTC timestamps. Timestamps describe record creation/observation and never participate in stable IDs.
- Large source or normalized bodies may later move to object storage; records therefore refer to content-addressed artifacts rather than relying on inline storage.

## 2. Common value objects

### Deterministic identifier

Identifier scheme version 1, accepted in ADR 0002, uses the printable form:

```text
<readable-prefix><lowercase-hex-sha256>
```

The prefixes are `repo_`, `ver_`, `file_`, `unit_`, `norm_`, `gene_`, `occ_`, `edge_`, `fam_`, and `run_`. The 64-character digest is SHA-256 over this envelope:

```json
{"fields": {"...": "kind-specific fields"}, "kind": "...", "scheme_version": 1}
```

Serialization is compact JSON with lexicographically sorted object keys, no insignificant whitespace, UTF-8 encoding, and non-ASCII characters emitted directly. All keys and string values are normalized to Unicode NFC before serialization. Only null, booleans, integers, strings, arrays, and string-keyed objects are allowed; floating-point values are forbidden. Arrays preserve order unless the field contract below declares them to be a set, in which case values are deduplicated and sorted first. Null and absent values are distinct. A collision between two object keys after NFC normalization is invalid.

Repository URL normalization is transport-independent for supported network Git URLs (`git`, `http`, `https`, `ssh`, and SCP-style SSH). It lowercases and IDNA-normalizes the host, removes the scheme, credentials, trailing host dot, and default port, normalizes the supplied owner/namespace and repository name using NFC plus Unicode case folding, removes one terminal `.git`, and verifies that the URL path matches the normalized owner/name. Query strings, fragments, local/file URLs, and path traversal are rejected. A non-default port remains identity-bearing.

Local repository identity follows ADR 0004. A local repository with a supported network `origin`
uses that origin's unchanged network RepositoryID v1. Without such an origin, local RepositoryID v2
hashes the resolved absolute POSIX path in a `local_repository` envelope. Local v2 identity is stable
on that filesystem but is not portable across path moves.

Repository-relative file paths are NFC-normalized, convert `\` to `/`, remove repeated separators and `.` segments, and reject absolute paths, drive-qualified paths, empty paths, and `..` traversal. Path case is preserved.

### Provenance

Every generated feature or derived relation contains:

| Field | Meaning |
|---|---|
| `algorithm` | Stable algorithm name |
| `algorithm_version` | Semantic or immutable implementation version |
| `configuration_id` | Deterministic effective-configuration identity |
| `created_at` | UTC creation time, excluded from identity |
| `toolchain` | Optional parser/compiler/library name and version |
| `input_ids` | Ordered or explicitly set-valued deterministic inputs |

### Source span

Uses zero-based byte offsets as the canonical location and records one-based line/column values for display. End offsets are exclusive. Encoding and newline normalization are explicit. Byte offsets plus content digest avoid locale-dependent identity.

## 3. Domain objects and important fields

### RepositoryRecord

- `repository_id`: derived from normalized Git `host`, optional non-default `port`, normalized `owner`, and normalized repository `name`.
- `canonical_locator`: normalized Git URL or declared local repository identity.
- `source_kind`: `network` or `local`; credential-free `acquisition_locator` used for updates.
- `display_name`, `default_branch`.
- `remote_fingerprint`: optional host/repository fingerprint.
- acquisition status and last observed/fetched timestamps.
- `schema_version`.

Credentials are never stored. Moving a repository between hosting URLs may require an explicit alias to preserve identity; URL equivalence must not be guessed silently.

The deterministic mirror cache and workspace paths are derived only from RepositoryID. Acquisition
status is `registered`, `ready`, or `failed`; successful acquisition records the observed object
format and HEAD without making either field identity-bearing.

### VersionRecord

- `version_id`: derived from `repository_id`, Git object format (`sha1` or `sha256`), and the full lowercase commit hash.
- `repository_id`, `commit_sha`.
- `aliases`: tags/release labels/branches observed for the commit.
- author/committer timestamps as source metadata.
- parent commit SHAs.
- selection policy and deterministic sequence position.
- materialization and analysis status.

Multiple aliases resolving to one commit share one VersionRecord.

### SourceFileRecord

- `source_file_id`: derived from `version_id` and canonical repository-relative POSIX path.
- `version_id`, `repository_id`, `path`.
- byte-content digest, size, encoding/newline observations.
- detected language and confidence.
- generated-code classification and evidence.
- discovery configuration and status.

The same bytes at two paths are two source-file contexts but can reference the same content artifact.

### CandidateUnit

- `candidate_unit_id`: derived from `source_file_id`, analyzer name/version, normalized unit kind, and canonical start/end byte offsets.
- `source_file_id`, `language`, `unit_kind` (`function` or `method`).
- original qualified/name information.
- source/declaration/body spans.
- inputs/outputs/type information when available.
- parser/analyzer provenance.
- raw-source artifact reference or digest.
- extraction status and diagnostics.

### NormalizedUnit

- `normalized_unit_id`: derived from `candidate_unit_id`, normalization algorithm/version, and normalization configuration version.
- `candidate_unit_id`, language, normalization provenance.
- normalized-code artifact/digest.
- normalized token artifact/digest and token count.
- identifier mapping summary, typed-literal summary, warnings.
- normalized representation schema version.

Normalization output is retained even when a subsequent filter rejects the candidate.

### GeneFeatures

A feature-set document groups compatible features for one normalized unit:

- `feature_set_id`: derived from `normalized_unit_id` plus ordered extractor contracts/configuration.
- `normalized_unit_id`.
- `features`: keyed values, each with its own provenance and availability state.
- required initial values: normalized code hash, normalized token digest/sequence reference, fuzzy hash, AST summary, CFG summary, call set, LOC, cyclomatic complexity, Halstead metrics, and maintainability index.
- extraction warnings and completeness state.

Missing, unsupported, failed, and computed-zero are distinct states.

### CoreIdentity

- `identity_scheme`, `identity_scheme_version`.
- language.
- normalization contract name/version.
- SHA-256 digest of the NFC-normalized, already-normalized core-code bytes.
- canonical envelope digest.
- `gene_id` computed from the envelope.

CoreIdentity excludes repository, version, commit, path, original symbol name, source span, timestamps, call-site context, fuzzy similarity, and display metadata.

### ContextIdentity

- `context_id`: derived from the context identity envelope.
- `repository_id`, `version_id`, `source_file_id`.
- candidate source byte span and occurrence kind.
- original qualified/function name, module/path, display line/column.
- input/output types, calling context, called functions where available.
- context extraction provenance.

The stable `occurrence_id` is derived from `gene_id` plus `candidate_unit_id`. Candidate identity supplies the immutable file, analyzer, unit kind, and source-span locator. Enrichable context fields such as resolved callers do not change it.

### SoftwareGene

- `gene_id`.
- embedded canonical CoreIdentity.
- canonical normalized representation/artifact reference.
- representative compatible feature-set references.
- `created_at`, `schema_version`, lifecycle/compatibility flags.

There is exactly one gene body for a GeneID under one identity scheme. Gene bodies are not overwritten when algorithms change; compatible projections are appended or stored separately.

### GeneOccurrence

- `occurrence_id`.
- `gene_id`, `repository_id`, `version_id`, `source_file_id`, `candidate_unit_id`.
- embedded ContextIdentity or `context_id` plus display projection.
- normalization/feature-set references.
- filter decision and acceptance evidence.
- observation run and timestamps.

One source candidate normally produces at most one accepted occurrence for an identity scheme. Different identity-scheme versions may coexist and must be queryable explicitly.

### GeneStatistics

- `statistics_id`: derived from `gene_id`, statistics algorithm/version, configuration, and scope.
- `gene_id`, scope (global/repository/version).
- occurrence, repository, version, and path counts.
- first/last observed version metadata where meaningful.
- recomputation watermark and provenance.

Statistics are rebuildable materialized views, never identity inputs.

### EvolutionEdge

- `evolution_edge_id`: derived from repository ID; nullable from/to version IDs; relation type; sorted unique source/target occurrence-ID sets; algorithm name/version; and configuration version.
- repository/comparison scope; from/to VersionIDs.
- `relation_type`: `birth`, `retention`, `mutation`, `migration`, `split`, `merge`, or `disappearance`.
- source and target occurrence/GeneID arrays.
- score, evidence features, thresholds, provenance.
- ambiguity/rank and review state if later introduced.

Birth has no source; disappearance has no target. Split and merge use sorted ID arrays, not pairwise edges pretending to be a group relation.

### GeneFamily

- `family_id`: derived from the sorted unique member GeneID set, family algorithm name/version, and configuration version.
- family-build/algorithm provenance.
- representative GeneID and aggregate evidence.
- member count and status.

Family identity is algorithm-relative; it is not a permanent replacement for GeneID.

### FamilyMember

- `family_member_id`: derived from `family_id` and `gene_id`.
- `family_id`, `gene_id`.
- role, similarity score, evidence, provenance.

### PipelineRun

- `pipeline_run_id`: derived from repository ID, the sorted unique selected VersionID set, pipeline version, `configuration_id`, and an explicit deterministic idempotency key. Reusing the key resumes/observes the same run; a deliberate new execution uses a new caller-supplied key.
- requested repository/version scope and `configuration_id`.
- pipeline/application version.
- status: queued, running, partially_succeeded, succeeded, failed, or cancelled.
- stage checkpoints, counters, timestamps, owner/lease data.
- parent/resumed run reference and error summary.

Outputs remain idempotent because their IDs derive from inputs, not PipelineRunID.

### ProcessingFailure

- `failure_id`: derived from optional PipelineRunID, stage, target ID, attempt, and deterministic diagnostic fingerprint.
- `pipeline_run_id` may be absent for direct repository acquisition commands that occur before a
  pipeline run exists.
- severity, stage, target kind/ID.
- stable error code and sanitized message.
- tool/parser diagnostic details and bounded stderr excerpt.
- retryability, attempt, first/last occurrence timestamps.
- correlation fields and resolved/superseded state.

Failures never include repository secrets or unbounded source/process output.

## 4. Relationships

```text
RepositoryRecord 1 ── * VersionRecord 1 ── * SourceFileRecord
                                            1
                                            └── * CandidateUnit
                                                     1
                                                     ├── * NormalizedUnit
                                                     │       └── * GeneFeatures
                                                     └── 0..* GeneOccurrence * ── 1 SoftwareGene

SoftwareGene 1 ── * GeneStatistics
GeneOccurrence * ── * EvolutionEdge (through source/target ID arrays)
SoftwareGene * ── * GeneFamily (through FamilyMember)
PipelineRun 1 ── * ProcessingFailure
```

Candidate, normalized, and feature records are separately retained for auditability and selective recomputation. A production retention policy may archive heavy artifacts without removing their digests or provenance.

## 5. Stable identifier rules

### Scheme-version 1 field contract

| ID | Prefix | Exact identity-bearing fields |
|---|---|---|
| RepositoryID | `repo_` | normalized Git host; optional non-default port; normalized owner/namespace; normalized repository name |
| Local RepositoryID v2 | `repo_` | resolved absolute POSIX repository path; only when no supported network origin exists |
| VersionID | `ver_` | RepositoryID; Git object format; full commit hash |
| SourceFileID | `file_` | VersionID; normalized repository-relative POSIX path |
| CandidateUnitID | `unit_` | SourceFileID; analyzer name; analyzer version; lowercased unit kind; zero-based start byte; exclusive end byte |
| NormalizedUnitID | `norm_` | CandidateUnitID; normalization algorithm; normalization version; normalization configuration version |
| GeneID | `gene_` | lowercased language; normalization algorithm; normalization version; SHA-256 of NFC-normalized canonical core code |
| OccurrenceID | `occ_` | GeneID; CandidateUnitID |
| EvolutionEdgeID | `edge_` | RepositoryID; nullable from/to VersionIDs; lowercased relation type; sorted unique source/target OccurrenceID sets; algorithm; algorithm version; configuration version |
| FamilyID | `fam_` | sorted unique GeneID member set; algorithm; algorithm version; configuration version |
| PipelineRunID | `run_` | RepositoryID; sorted unique VersionID scope; pipeline version; ConfigurationID; caller-supplied idempotency key |

GeneID is deliberately core-only. Repository, version, commit, file path, source location, original names, callers/callees, types used only as context, timestamps, feature scores, family/evolution membership, database IDs, and run IDs do not participate. The identity layer does not normalize C/C++: it accepts the canonical code produced by a separately versioned normalizer. Consequently, two raw functions that differ only by a local-variable rename receive the same GeneID only when normalization produces the same canonical core code.

Additional rules:

1. Include `kind` and scheme version in every envelope to prevent cross-type collisions.
2. Use full Git object IDs with their hash algorithm, never abbreviated SHAs or tag text.
3. Preserve file-path case because Git paths may be case-sensitive.
4. Exclude timestamps, processing hosts, mutable repository metadata such as stars/descriptions, and MongoDB identifiers.
5. Algorithm behavior changes require a new algorithm version even if the name is unchanged.
6. Identity-scheme changes require an ADR and coexistence/migration plan; never rewrite identifiers in place.
7. MongoDB `_id` may mirror the deterministic domain ID but is never its source.

## 6. Proposed MongoDB collections and indexes

All collection names are plural snake_case. Every collection has `{schema_version: 1}` initially. Index creation belongs to a versioned migration.

### Primary and evidence collections

| Collection | Primary document key | Important indexes |
|---|---|---|
| `repositories` | `_id = repository_id` | unique `canonical_locator`; `acquisition.status` |
| `versions` | `_id = version_id` | unique `(repository_id, commit_sha)`; `(repository_id, sequence.position)`; multikey `(repository_id, aliases.name)` |
| `source_files` | `_id = source_file_id` | unique `(version_id, path)`; `(version_id, language, generated.status)`; `content_digest` |
| `candidate_units` | `_id = candidate_unit_id` | `(source_file_id, source_span.start_byte)`; `(source_file_id, extraction_status)` |
| `normalized_units` | `_id = normalized_unit_id` | unique `(candidate_unit_id, algorithm, algorithm_version, configuration_id)`; `normalized_code_digest`; `normalized_token_digest` |
| `gene_features` | `_id = feature_set_id` | `(normalized_unit_id, completeness)`; sparse indexes for explicitly supported similarity-query projections |
| `genes` | `_id = gene_id` | unique `gene_id`; `core_identity.canonical_envelope_digest`; `(core_identity.identity_scheme_version, core_identity.language)` |
| `gene_occurrences` | `_id = occurrence_id` | unique `(gene_id, candidate_unit_id)`; `(version_id, source_file_id)`; `(gene_id, repository_id, version_id)`; `(candidate_unit_id, identity_scheme_version)` |
| `gene_statistics` | `_id = statistics_id` | unique `(gene_id, scope.kind, scope.id, algorithm_version, configuration_id)`; selected descending count indexes only after query measurement |
| `evolution_edges` | `_id = evolution_edge_id` | `(repository_id, from_version_id, to_version_id, relation_type)`; multikey `source_gene_ids`; multikey `target_gene_ids`; `(comparison_id, algorithm_version)` |
| `gene_families` | `_id = family_id` | `(family_build_id, representative_gene_id)`; `(algorithm, algorithm_version)` |
| `family_members` | `_id = family_member_id` | unique `(family_id, gene_id)`; `(gene_id, family_build_id)` |

### Operations and compatibility collections

| Collection | Primary document key | Important indexes |
|---|---|---|
| `configurations` | `_id = configuration_id` | `(created_at)`; unique canonical digest |
| `pipeline_runs` | `_id = pipeline_run_id` | `(status, created_at)`; `(scope.repository_id, created_at)`; `(lease.expires_at)` |
| `stage_work_items` | deterministic work-item ID | unique `(stage, input_id, compatibility_key)`; `(status, lease.expires_at)`; `(pipeline_run_id, stage)` |
| `processing_failures` | `_id = failure_id` | `(pipeline_run_id, stage, severity)`; `(target_kind, target_id)`; `(error_code, last_seen_at)` |
| `schema_migrations` | `_id = migration_id` | unique `(version)` |
| `family_builds` | `_id = family_build_id` | `(status, algorithm, algorithm_version)` |
| `version_comparisons` | `_id = comparison_id` | unique `(repository_id, from_version_id, to_version_id, algorithm_version, configuration_id)` |

### Index cautions

- Do not create every speculative metric index initially; indexes add substantial write and storage cost.
- MongoDB cannot efficiently support every high-dimensional similarity method with ordinary indexes. The first implementation may use deterministic bounded candidate generation; the long-term similarity index remains a technical decision.
- Large AST, CFG, token, or source artifacts must remain below MongoDB's document limit. Prefer content-addressed external artifacts or GridFS only after the artifact-storage decision is made.
- Use partial indexes for active leases and actionable failures where supported and verified.

## 7. Write and consistency rules

- Gene-body creation is an upsert keyed by GeneID; a conflicting core envelope for an existing GeneID is a fatal integrity diagnostic.
- Occurrence upsert follows successful gene-body upsert. MongoDB transactions may be used when configured as a replica set, but reconciliation must also repair interrupted two-step writes.
- Stage completion is conditional on required output IDs being durable. A lease owner uses compare-and-set updates to finalize work.
- Derived statistics are rebuilt from occurrences or updated using idempotency tokens; they are never the sole evidence.
- Deleting or superseding an algorithm projection must not cascade-delete immutable source evidence.

## 8. Persistence contract

The MongoDB adapter implements driver-independent repository protocols owned by the application boundary. Domain modules and protocols do not import PyMongo. Each of the following collections has an explicit serializer, deserializer, deterministic storage key, and typed repository: `repositories`, `versions`, `source_files`, `candidate_units`, `normalized_units`, `gene_features`, `genes`, `gene_occurrences`, `gene_statistics`, `evolution_edges`, `gene_families`, `family_members`, `pipeline_runs`, and `processing_failures`.

Single-identity records use their deterministic domain identifier as MongoDB `_id`; family members use the deterministic composite of `(family_id, gene_id)`. `_id` is a storage mirror or composite key, never a generated ObjectId and never an input to domain identity.

Writes use full-document replacement upserts filtered by `_id`. Bulk writes use ordered replacement upserts. Repeating an identical write creates no additional document, and retrying a partially completed bulk converges because every operation has a deterministic key. Deserializers verify that `_id` agrees with the record's identity fields.

Pagination is keyset-based: documents are sorted by ascending `_id`, and the opaque `next_cursor` is the final `_id` on the returned page when another page exists. Page sizes are limited to 1–1000; offset pagination is not used.

Collection initialization is idempotent and creates the declared collections and named indexes. In addition to unique identity indexes, query indexes cover versions by `(repository_id, commit_time)`, occurrences by `(repository_id, version_id)`, `gene_id`, and `relative_path`, evolution edge multikey fields `source_gene_ids` and `target_gene_ids`, and statistics by descending `project_count` and `version_count`.

MongoDB operations retry only recognized transient network, topology, timeout, retry-labelled, and transient server-code errors. Retries use bounded exponential backoff. Exhausted transient failures and non-transient driver failures are translated into driver-independent persistence errors.
