# ADR 0004: Git Repository Acquisition Contract

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** Geno project maintainers

## Context

Geno must register and update local and network Git repositories without coupling application logic
to subprocesses or MongoDB. Repository acquisition handles untrusted locators, may receive temporary
credentials, and must produce deterministic cache locations and structured durable failures.

ADR 0002 froze network RepositoryID scheme version 1 but did not define identity for a local-only
repository with no network origin. Reinterpreting network v1 would violate the identifier contract.

## Decision

Network locators supported by the acquisition adapter are HTTP, HTTPS, native Git, URI-form SSH,
and SCP-form SSH. The existing transport-independent network RepositoryID v1 is unchanged. Nested
namespaces support GitHub, GitLab, Gitee, and generic Git hosts without host-specific branching.

A local repository with a supported `origin` URL receives the same network RepositoryID as that
origin while its local canonical path remains the acquisition source. A local repository without a
usable network origin receives a local RepositoryID scheme version 2. Its exact envelope is:

```json
{"fields":{"canonical_path":"<resolved absolute POSIX path>"},"kind":"local_repository","scheme_version":2}
```

The v2 local identity is deterministic on one filesystem but intentionally does not claim
portability when the same repository is moved to another absolute path. Adding an origin and
re-registering may therefore establish a distinct, portable network identity; aliases remain a
future decision.

Each RepositoryID maps to `<repository-cache>/<RepositoryID>.git` and
`<workspace>/<RepositoryID>`. Acquisition uses a bare mirror clone built in a temporary sibling and
atomically renamed into place. Updates fetch and prune the mirror. Reference and commit reads occur
only against the local mirror.

Git runs through a typed adapter using subprocess argument arrays, `shell=False`, non-interactive
prompt settings, captured UTF-8 output, and a configurable timeout. Geno never executes repository
content. Structured failures include a stable code, operation, retryability, exit code, and bounded
stderr.

Credentials may be used transiently for the initial network command but are removed from the
persisted acquisition locator and the mirror's stored `origin`. Commands are not logged. Error text
and stderr are redacted and bounded before CLI display or MongoDB persistence. Direct acquisition
failures may have no PipelineRunID because repository CLI operations can precede a pipeline run.

## Consequences

- Re-registering and updating a repository converge on one record and one mirror cache.
- HTTPS and SSH forms of one network repository retain the same v1 identity.
- Credential helpers and SSH agents remain the preferred way to authenticate updates because Geno
  does not retain plaintext credentials.
- Local-only identity is host-path scoped and must not be presented as portable provenance.
- Concurrent first clones converge through atomic rename; later orchestration may add an explicit
  inter-process lock if concurrent update throughput requires it.

## Compatibility and migration

All existing network v1 golden vectors remain unchanged. Local v2 identifiers coexist with network
v1 identifiers under the `repo_` prefix and are distinguishable through their canonical envelopes.
No production local repository records existed, so no migration is required.
