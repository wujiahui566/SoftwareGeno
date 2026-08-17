"""Typed persistence records shared by domain and infrastructure boundaries."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from geno.identity import (
    CandidateUnitId,
    EvolutionEdgeId,
    FamilyId,
    GeneId,
    NormalizedUnitId,
    OccurrenceId,
    PipelineRunId,
    RepositoryId,
    SourceFileId,
    VersionId,
)

NonEmptyText = Annotated[str, Field(min_length=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveSchemaVersion = Annotated[int, Field(ge=1)]


class DomainRecord(BaseModel):
    """Base behavior for immutable, validated persistence records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: PositiveSchemaVersion = 1


class RepositoryRecord(DomainRecord):
    repository_id: RepositoryId
    canonical_locator: NonEmptyText
    owner: NonEmptyText
    name: NonEmptyText
    default_branch: str | None = None
    source_kind: Literal["network", "local"] = "network"
    acquisition_locator: NonEmptyText | None = None
    acquisition_status: Literal["registered", "ready", "failed"] = "registered"
    last_acquired_at: AwareDatetime | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class VersionRecord(DomainRecord):
    version_id: VersionId
    repository_id: RepositoryId
    commit_hash: NonEmptyText
    commit_time: AwareDatetime
    aliases: tuple[str, ...] = ()
    parent_commit_hashes: tuple[str, ...] = ()


class SourceFileRecord(DomainRecord):
    source_file_id: SourceFileId
    repository_id: RepositoryId
    version_id: VersionId
    relative_path: NonEmptyText
    content_sha256: NonEmptyText
    language: NonEmptyText
    generated: bool = False


class CandidateUnitRecord(DomainRecord):
    candidate_unit_id: CandidateUnitId
    source_file_id: SourceFileId
    analyzer: NonEmptyText
    analyzer_version: NonEmptyText
    unit_kind: NonEmptyText
    start_byte: NonNegativeInt
    end_byte: Annotated[int, Field(gt=0)]
    original_name: str | None = None

    @model_validator(mode="after")
    def validate_source_span(self) -> Self:
        if self.end_byte <= self.start_byte:
            msg = "candidate source span must satisfy start_byte < end_byte"
            raise ValueError(msg)
        return self


class NormalizedUnitRecord(DomainRecord):
    normalized_unit_id: NormalizedUnitId
    candidate_unit_id: CandidateUnitId
    normalization_algorithm: NonEmptyText
    normalization_version: NonEmptyText
    configuration_version: NonEmptyText
    normalized_code_sha256: NonEmptyText
    normalized_token_sha256: str | None = None


class GeneFeatureRecord(DomainRecord):
    feature_set_id: NonEmptyText
    normalized_unit_id: NormalizedUnitId
    algorithm: NonEmptyText
    algorithm_version: NonEmptyText
    configuration_version: NonEmptyText
    created_at: AwareDatetime
    values: dict[str, JsonValue] = Field(default_factory=dict)


class GeneRecord(DomainRecord):
    gene_id: GeneId
    language: NonEmptyText
    normalization_algorithm: NonEmptyText
    normalization_version: NonEmptyText
    normalized_code_sha256: NonEmptyText
    feature_set_ids: tuple[str, ...] = ()


class GeneOccurrenceRecord(DomainRecord):
    occurrence_id: OccurrenceId
    gene_id: GeneId
    repository_id: RepositoryId
    version_id: VersionId
    source_file_id: SourceFileId
    candidate_unit_id: CandidateUnitId
    relative_path: NonEmptyText
    original_name: str | None = None


class GeneStatisticsRecord(DomainRecord):
    statistics_id: NonEmptyText
    gene_id: GeneId
    project_count: NonNegativeInt
    version_count: NonNegativeInt
    occurrence_count: NonNegativeInt
    algorithm_version: NonEmptyText
    configuration_version: NonEmptyText


class EvolutionEdgeRecord(DomainRecord):
    evolution_edge_id: EvolutionEdgeId
    repository_id: RepositoryId
    from_version_id: VersionId | None
    to_version_id: VersionId | None
    relation_type: NonEmptyText
    source_gene_ids: tuple[GeneId, ...] = ()
    target_gene_ids: tuple[GeneId, ...] = ()
    source_occurrence_ids: tuple[OccurrenceId, ...] = ()
    target_occurrence_ids: tuple[OccurrenceId, ...] = ()
    algorithm: NonEmptyText
    algorithm_version: NonEmptyText
    configuration_version: NonEmptyText
    score: float | None = None


class GeneFamilyRecord(DomainRecord):
    family_id: FamilyId
    algorithm: NonEmptyText
    algorithm_version: NonEmptyText
    configuration_version: NonEmptyText
    representative_gene_id: GeneId
    member_count: NonNegativeInt


class FamilyMemberRecord(DomainRecord):
    family_id: FamilyId
    gene_id: GeneId
    role: NonEmptyText = "member"
    similarity_score: float | None = None
    evidence: dict[str, JsonValue] = Field(default_factory=dict)


class PipelineRunRecord(DomainRecord):
    pipeline_run_id: PipelineRunId
    repository_id: RepositoryId
    version_ids: tuple[VersionId, ...]
    configuration_id: NonEmptyText
    pipeline_version: NonEmptyText
    status: Literal[
        "queued",
        "running",
        "partially_succeeded",
        "succeeded",
        "failed",
        "cancelled",
    ]
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ProcessingFailureRecord(DomainRecord):
    failure_id: NonEmptyText
    pipeline_run_id: PipelineRunId | None = None
    stage: NonEmptyText
    target_kind: NonEmptyText
    target_id: NonEmptyText
    error_code: NonEmptyText
    message: NonEmptyText
    retryable: bool
    attempt: Annotated[int, Field(ge=1)]
    occurred_at: AwareDatetime
    details: dict[str, JsonValue] = Field(default_factory=dict)


PersistedRecord = (
    RepositoryRecord
    | VersionRecord
    | SourceFileRecord
    | CandidateUnitRecord
    | NormalizedUnitRecord
    | GeneFeatureRecord
    | GeneRecord
    | GeneOccurrenceRecord
    | GeneStatisticsRecord
    | EvolutionEdgeRecord
    | GeneFamilyRecord
    | FamilyMemberRecord
    | PipelineRunRecord
    | ProcessingFailureRecord
)
