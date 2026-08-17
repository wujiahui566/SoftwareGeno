"""Typed constructors for Geno deterministic domain identifiers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Final, NewType

from geno.identity.canonical import canonical_json_bytes, normalize_unicode
from geno.identity.normalization import normalize_git_repository, normalize_relative_path

RepositoryId = NewType("RepositoryId", str)
VersionId = NewType("VersionId", str)
SourceFileId = NewType("SourceFileId", str)
CandidateUnitId = NewType("CandidateUnitId", str)
NormalizedUnitId = NewType("NormalizedUnitId", str)
GeneId = NewType("GeneId", str)
OccurrenceId = NewType("OccurrenceId", str)
EvolutionEdgeId = NewType("EvolutionEdgeId", str)
FamilyId = NewType("FamilyId", str)
PipelineRunId = NewType("PipelineRunId", str)

Identifier = (
    RepositoryId
    | VersionId
    | SourceFileId
    | CandidateUnitId
    | NormalizedUnitId
    | GeneId
    | OccurrenceId
    | EvolutionEdgeId
    | FamilyId
    | PipelineRunId
)

IDENTIFIER_SCHEME_VERSION: Final = 1
LOCAL_REPOSITORY_IDENTIFIER_SCHEME_VERSION: Final = 2
_FULL_HEX = re.compile(r"^[0-9a-f]+$")


def create_repository_id(git_url: str, *, owner: str, name: str) -> RepositoryId:
    """Create an ID from normalized Git host/port, owner, and repository name."""
    repository = normalize_git_repository(git_url, owner=owner, name=name)
    return RepositoryId(
        _create_identifier(
            "repository",
            "repo_",
            {
                "host": repository.host,
                "port": repository.port,
                "owner": repository.owner,
                "name": repository.name,
            },
        )
    )


def create_local_repository_id(*, canonical_path: str) -> RepositoryId:
    """Create a v2 ID for a local repository that has no network identity.

    Network RepositoryID v1 remains frozen. Local-only identity is deliberately
    scoped to the canonical absolute path and therefore is stable on one host but
    does not claim portability across filesystem layouts.
    """
    path = normalize_unicode(canonical_path.strip())
    if not path:
        msg = "canonical_path cannot be empty"
        raise ValueError(msg)
    return RepositoryId(
        _create_identifier(
            "local_repository",
            "repo_",
            {"canonical_path": path},
            scheme_version=LOCAL_REPOSITORY_IDENTIFIER_SCHEME_VERSION,
        )
    )


def create_version_id(
    repository_id: RepositoryId,
    *,
    commit_hash: str,
    git_object_format: str = "sha1",
) -> VersionId:
    """Create an ID from repository identity and a full Git commit object ID."""
    object_format = _casefold_text(git_object_format, "git_object_format")
    expected_length = {"sha1": 40, "sha256": 64}.get(object_format)
    normalized_hash = commit_hash.casefold()
    if (
        expected_length is None
        or len(normalized_hash) != expected_length
        or not _FULL_HEX.fullmatch(normalized_hash)
    ):
        msg = "commit hash must be a full lowercase-compatible SHA-1 or SHA-256 object ID"
        raise ValueError(msg)
    return VersionId(
        _create_identifier(
            "version",
            "ver_",
            {
                "repository_id": repository_id,
                "git_object_format": object_format,
                "commit_hash": normalized_hash,
            },
        )
    )


def create_source_file_id(version_id: VersionId, *, relative_path: str) -> SourceFileId:
    """Create an ID from version identity and canonical repository-relative path."""
    return SourceFileId(
        _create_identifier(
            "source_file",
            "file_",
            {
                "version_id": version_id,
                "relative_path": normalize_relative_path(relative_path),
            },
        )
    )


def create_candidate_unit_id(
    source_file_id: SourceFileId,
    *,
    analyzer: str,
    analyzer_version: str,
    unit_kind: str,
    start_byte: int,
    end_byte: int,
) -> CandidateUnitId:
    """Create an ID from a file, analyzer contract, unit kind, and byte span."""
    _validate_span(start_byte, end_byte)
    return CandidateUnitId(
        _create_identifier(
            "candidate_unit",
            "unit_",
            {
                "source_file_id": source_file_id,
                "analyzer": _required_text(analyzer, "analyzer"),
                "analyzer_version": _required_text(analyzer_version, "analyzer_version"),
                "unit_kind": _casefold_text(unit_kind, "unit_kind"),
                "start_byte": start_byte,
                "end_byte": end_byte,
            },
        )
    )


def create_normalized_unit_id(
    candidate_unit_id: CandidateUnitId,
    *,
    normalization_algorithm: str,
    normalization_version: str,
    configuration_version: str,
) -> NormalizedUnitId:
    """Create an ID from a candidate and its complete normalization contract."""
    return NormalizedUnitId(
        _create_identifier(
            "normalized_unit",
            "norm_",
            {
                "candidate_unit_id": candidate_unit_id,
                "normalization_algorithm": _required_text(
                    normalization_algorithm, "normalization_algorithm"
                ),
                "normalization_version": _required_text(
                    normalization_version, "normalization_version"
                ),
                "configuration_version": _required_text(
                    configuration_version, "configuration_version"
                ),
            },
        )
    )


def create_gene_id(
    *,
    language: str,
    normalization_algorithm: str,
    normalization_version: str,
    normalized_core_code: str,
) -> GeneId:
    """Create a core-only GeneID from an already-normalized source representation."""
    canonical_core = normalize_unicode(normalized_core_code).encode("utf-8")
    normalized_code_sha256 = hashlib.sha256(canonical_core).hexdigest()
    return GeneId(
        _create_identifier(
            "gene",
            "gene_",
            {
                "language": _casefold_text(language, "language"),
                "normalization_algorithm": _required_text(
                    normalization_algorithm, "normalization_algorithm"
                ),
                "normalization_version": _required_text(
                    normalization_version, "normalization_version"
                ),
                "normalized_code_sha256": normalized_code_sha256,
            },
        )
    )


def create_occurrence_id(
    gene_id: GeneId,
    *,
    candidate_unit_id: CandidateUnitId,
) -> OccurrenceId:
    """Create an ID locating a gene at one extracted candidate context."""
    return OccurrenceId(
        _create_identifier(
            "occurrence",
            "occ_",
            {"gene_id": gene_id, "candidate_unit_id": candidate_unit_id},
        )
    )


def create_evolution_edge_id(
    *,
    repository_id: RepositoryId,
    from_version_id: VersionId | None,
    to_version_id: VersionId | None,
    relation_type: str,
    source_occurrence_ids: Sequence[OccurrenceId],
    target_occurrence_ids: Sequence[OccurrenceId],
    algorithm: str,
    algorithm_version: str,
    configuration_version: str,
) -> EvolutionEdgeId:
    """Create an ID for a versioned evolution relation and its complete member sets."""
    sources = _sorted_unique(source_occurrence_ids, "source_occurrence_ids", allow_empty=True)
    targets = _sorted_unique(target_occurrence_ids, "target_occurrence_ids", allow_empty=True)
    relation = _casefold_text(relation_type, "relation_type")
    _validate_evolution_shape(
        relation,
        from_version_id=from_version_id,
        to_version_id=to_version_id,
        sources=sources,
        targets=targets,
    )
    return EvolutionEdgeId(
        _create_identifier(
            "evolution_edge",
            "edge_",
            {
                "repository_id": repository_id,
                "from_version_id": from_version_id,
                "to_version_id": to_version_id,
                "relation_type": relation,
                "source_occurrence_ids": sources,
                "target_occurrence_ids": targets,
                "algorithm": _required_text(algorithm, "algorithm"),
                "algorithm_version": _required_text(algorithm_version, "algorithm_version"),
                "configuration_version": _required_text(
                    configuration_version, "configuration_version"
                ),
            },
        )
    )


def create_family_id(
    *,
    gene_ids: Sequence[GeneId],
    algorithm: str,
    algorithm_version: str,
    configuration_version: str,
) -> FamilyId:
    """Create an algorithm-relative ID from a complete unordered gene-member set."""
    return FamilyId(
        _create_identifier(
            "family",
            "fam_",
            {
                "gene_ids": _sorted_unique(gene_ids, "gene_ids"),
                "algorithm": _required_text(algorithm, "algorithm"),
                "algorithm_version": _required_text(algorithm_version, "algorithm_version"),
                "configuration_version": _required_text(
                    configuration_version, "configuration_version"
                ),
            },
        )
    )


def create_pipeline_run_id(
    *,
    repository_id: RepositoryId,
    version_ids: Sequence[VersionId],
    pipeline_version: str,
    configuration_id: str,
    idempotency_key: str,
) -> PipelineRunId:
    """Create an ID from deterministic execution scope and caller idempotency key."""
    return PipelineRunId(
        _create_identifier(
            "pipeline_run",
            "run_",
            {
                "repository_id": repository_id,
                "version_ids": _sorted_unique(version_ids, "version_ids"),
                "pipeline_version": _required_text(pipeline_version, "pipeline_version"),
                "configuration_id": _required_text(configuration_id, "configuration_id"),
                "idempotency_key": _required_text(idempotency_key, "idempotency_key"),
            },
        )
    )


def _create_identifier(
    kind: str,
    prefix: str,
    fields: Mapping[str, object],
    *,
    scheme_version: int = IDENTIFIER_SCHEME_VERSION,
) -> str:
    envelope = {
        "kind": kind,
        "scheme_version": scheme_version,
        "fields": fields,
    }
    digest = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    return f"{prefix}{digest}"


def _required_text(value: str, field_name: str) -> str:
    normalized = normalize_unicode(value.strip())
    if not normalized:
        msg = f"{field_name} cannot be empty"
        raise ValueError(msg)
    return normalized


def _casefold_text(value: str, field_name: str) -> str:
    return normalize_unicode(_required_text(value, field_name).casefold())


def _validate_span(start_byte: int, end_byte: int) -> None:
    if isinstance(start_byte, bool) or isinstance(end_byte, bool):
        msg = "source byte offsets must be integers"
        raise TypeError(msg)
    if start_byte < 0 or end_byte <= start_byte:
        msg = "source byte span must satisfy 0 <= start_byte < end_byte"
        raise ValueError(msg)


def _sorted_unique[ID: str](
    values: Sequence[ID], field_name: str, *, allow_empty: bool = False
) -> list[ID]:
    unique = sorted(set(values))
    if not unique and not allow_empty:
        msg = f"{field_name} cannot be empty"
        raise ValueError(msg)
    return unique


def _validate_evolution_shape(
    relation: str,
    *,
    from_version_id: VersionId | None,
    to_version_id: VersionId | None,
    sources: Sequence[OccurrenceId],
    targets: Sequence[OccurrenceId],
) -> None:
    supported = {
        "birth",
        "retention",
        "mutation",
        "migration",
        "split",
        "merge",
        "disappearance",
    }
    if relation not in supported:
        msg = f"unsupported evolution relation: {relation!r}"
        raise ValueError(msg)
    if relation == "birth":
        valid = (
            from_version_id is None and not sources and to_version_id is not None and bool(targets)
        )
    elif relation == "disappearance":
        valid = (
            from_version_id is not None and bool(sources) and to_version_id is None and not targets
        )
    else:
        valid = (
            from_version_id is not None
            and to_version_id is not None
            and bool(sources)
            and bool(targets)
        )
    if not valid:
        msg = f"invalid source/target shape for evolution relation {relation!r}"
        raise ValueError(msg)
