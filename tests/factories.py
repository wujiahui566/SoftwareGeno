"""Deterministic persistence-record fixtures shared by unit and integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

from geno.domain import (
    CandidateUnitRecord,
    EvolutionEdgeRecord,
    FamilyMemberRecord,
    GeneFamilyRecord,
    GeneFeatureRecord,
    GeneOccurrenceRecord,
    GeneRecord,
    GeneStatisticsRecord,
    NormalizedUnitRecord,
    PipelineRunRecord,
    ProcessingFailureRecord,
    RepositoryRecord,
    SourceFileRecord,
    VersionRecord,
)
from geno.identity import (
    create_candidate_unit_id,
    create_evolution_edge_id,
    create_family_id,
    create_gene_id,
    create_normalized_unit_id,
    create_occurrence_id,
    create_pipeline_run_id,
    create_repository_id,
    create_source_file_id,
    create_version_id,
)

FIXED_TIME = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
FIRST_COMMIT = "0123456789abcdef0123456789abcdef01234567"
SECOND_COMMIT = "fedcba9876543210fedcba9876543210fedcba98"


def persistence_records() -> tuple[
    RepositoryRecord,
    VersionRecord,
    SourceFileRecord,
    CandidateUnitRecord,
    NormalizedUnitRecord,
    GeneFeatureRecord,
    GeneRecord,
    GeneOccurrenceRecord,
    GeneStatisticsRecord,
    EvolutionEdgeRecord,
    GeneFamilyRecord,
    FamilyMemberRecord,
    PipelineRunRecord,
    ProcessingFailureRecord,
]:
    repository_id = create_repository_id(
        "https://github.com/openai/geno.git", owner="openai", name="geno"
    )
    version_id = create_version_id(repository_id, commit_hash=FIRST_COMMIT)
    next_version_id = create_version_id(repository_id, commit_hash=SECOND_COMMIT)
    source_file_id = create_source_file_id(version_id, relative_path="src/gene.cpp")
    candidate_unit_id = create_candidate_unit_id(
        source_file_id,
        analyzer="clang-adapter",
        analyzer_version="1",
        unit_kind="function",
        start_byte=10,
        end_byte=90,
    )
    normalized_unit_id = create_normalized_unit_id(
        candidate_unit_id,
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        configuration_version="normalization-v1",
    )
    gene_id = create_gene_id(
        language="cpp",
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        normalized_core_code="int fn(int p0){return p0+<int>;}",
    )
    occurrence_id = create_occurrence_id(gene_id, candidate_unit_id=candidate_unit_id)
    edge_id = create_evolution_edge_id(
        repository_id=repository_id,
        from_version_id=version_id,
        to_version_id=next_version_id,
        relation_type="retention",
        source_occurrence_ids=[occurrence_id],
        target_occurrence_ids=[occurrence_id],
        algorithm="exact-gene-match",
        algorithm_version="1",
        configuration_version="evolution-v1",
    )
    family_id = create_family_id(
        gene_ids=[gene_id],
        algorithm="exact-gene",
        algorithm_version="1",
        configuration_version="families-v1",
    )
    pipeline_run_id = create_pipeline_run_id(
        repository_id=repository_id,
        version_ids=[version_id, next_version_id],
        pipeline_version="0.1.0",
        configuration_id="config_fixture_v1",
        idempotency_key="persistence-fixture",
    )

    repository = RepositoryRecord(
        repository_id=repository_id,
        canonical_locator="github.com/openai/geno",
        owner="openai",
        name="geno",
        default_branch="main",
        metadata={"stars": 42},
    )
    version = VersionRecord(
        version_id=version_id,
        repository_id=repository_id,
        commit_hash=FIRST_COMMIT,
        commit_time=FIXED_TIME,
        aliases=("v0.1.0",),
    )
    source_file = SourceFileRecord(
        source_file_id=source_file_id,
        repository_id=repository_id,
        version_id=version_id,
        relative_path="src/gene.cpp",
        content_sha256="a" * 64,
        language="cpp",
    )
    candidate = CandidateUnitRecord(
        candidate_unit_id=candidate_unit_id,
        source_file_id=source_file_id,
        analyzer="clang-adapter",
        analyzer_version="1",
        unit_kind="function",
        start_byte=10,
        end_byte=90,
        original_name="add_one",
    )
    normalized = NormalizedUnitRecord(
        normalized_unit_id=normalized_unit_id,
        candidate_unit_id=candidate_unit_id,
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        configuration_version="normalization-v1",
        normalized_code_sha256="b" * 64,
        normalized_token_sha256="c" * 64,
    )
    features = GeneFeatureRecord(
        feature_set_id="feature_fixture_v1",
        normalized_unit_id=normalized_unit_id,
        algorithm="fixture-features",
        algorithm_version="1",
        configuration_version="features-v1",
        created_at=FIXED_TIME,
        values={"loc": 3, "calls": ["malloc"]},
    )
    gene = GeneRecord(
        gene_id=gene_id,
        language="cpp",
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        normalized_code_sha256="b" * 64,
        feature_set_ids=(features.feature_set_id,),
    )
    occurrence = GeneOccurrenceRecord(
        occurrence_id=occurrence_id,
        gene_id=gene_id,
        repository_id=repository_id,
        version_id=version_id,
        source_file_id=source_file_id,
        candidate_unit_id=candidate_unit_id,
        relative_path="src/gene.cpp",
        original_name="add_one",
    )
    statistics = GeneStatisticsRecord(
        statistics_id="statistics_fixture_v1",
        gene_id=gene_id,
        project_count=1,
        version_count=2,
        occurrence_count=2,
        algorithm_version="1",
        configuration_version="statistics-v1",
    )
    edge = EvolutionEdgeRecord(
        evolution_edge_id=edge_id,
        repository_id=repository_id,
        from_version_id=version_id,
        to_version_id=next_version_id,
        relation_type="retention",
        source_gene_ids=(gene_id,),
        target_gene_ids=(gene_id,),
        source_occurrence_ids=(occurrence_id,),
        target_occurrence_ids=(occurrence_id,),
        algorithm="exact-gene-match",
        algorithm_version="1",
        configuration_version="evolution-v1",
        score=1.0,
    )
    family = GeneFamilyRecord(
        family_id=family_id,
        algorithm="exact-gene",
        algorithm_version="1",
        configuration_version="families-v1",
        representative_gene_id=gene_id,
        member_count=1,
    )
    member = FamilyMemberRecord(
        family_id=family_id,
        gene_id=gene_id,
        role="representative",
        similarity_score=1.0,
        evidence={"match": "exact"},
    )
    pipeline_run = PipelineRunRecord(
        pipeline_run_id=pipeline_run_id,
        repository_id=repository_id,
        version_ids=(version_id, next_version_id),
        configuration_id="config_fixture_v1",
        pipeline_version="0.1.0",
        status="succeeded",
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    failure = ProcessingFailureRecord(
        failure_id="failure_fixture_v1",
        pipeline_run_id=pipeline_run_id,
        stage="parse",
        target_kind="source_file",
        target_id=str(source_file_id),
        error_code="fixture_parse_failure",
        message="fixture diagnostic",
        retryable=False,
        attempt=1,
        occurred_at=FIXED_TIME,
        details={"line": 1},
    )
    return (
        repository,
        version,
        source_file,
        candidate,
        normalized,
        features,
        gene,
        occurrence,
        statistics,
        edge,
        family,
        member,
        pipeline_run,
        failure,
    )
