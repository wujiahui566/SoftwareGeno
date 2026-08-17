"""Version-1 MongoDB collection and index declarations."""

from __future__ import annotations

from typing import Final

from pymongo import ASCENDING, DESCENDING, IndexModel

COLLECTION_NAMES: Final[tuple[str, ...]] = (
    "repositories",
    "versions",
    "source_files",
    "candidate_units",
    "normalized_units",
    "gene_features",
    "genes",
    "gene_occurrences",
    "gene_statistics",
    "evolution_edges",
    "gene_families",
    "family_members",
    "pipeline_runs",
    "processing_failures",
)

COLLECTION_INDEXES: Final[dict[str, tuple[IndexModel, ...]]] = {
    "repositories": (
        IndexModel([("repository_id", ASCENDING)], unique=True, name="uq_repository_id"),
        IndexModel([("canonical_locator", ASCENDING)], unique=True, name="uq_canonical_locator"),
        IndexModel([("acquisition_status", ASCENDING)], name="ix_repository_acquisition_status"),
    ),
    "versions": (
        IndexModel([("version_id", ASCENDING)], unique=True, name="uq_version_id"),
        IndexModel(
            [("repository_id", ASCENDING), ("commit_time", DESCENDING)],
            name="ix_versions_repository_commit_time",
        ),
    ),
    "source_files": (
        IndexModel([("source_file_id", ASCENDING)], unique=True, name="uq_source_file_id"),
    ),
    "candidate_units": (
        IndexModel([("candidate_unit_id", ASCENDING)], unique=True, name="uq_candidate_unit_id"),
    ),
    "normalized_units": (
        IndexModel([("normalized_unit_id", ASCENDING)], unique=True, name="uq_normalized_unit_id"),
    ),
    "gene_features": (
        IndexModel([("feature_set_id", ASCENDING)], unique=True, name="uq_feature_set_id"),
        IndexModel([("normalized_unit_id", ASCENDING)], name="ix_features_normalized_unit"),
    ),
    "genes": (IndexModel([("gene_id", ASCENDING)], unique=True, name="uq_gene_id"),),
    "gene_occurrences": (
        IndexModel([("occurrence_id", ASCENDING)], unique=True, name="uq_occurrence_id"),
        IndexModel(
            [("repository_id", ASCENDING), ("version_id", ASCENDING)],
            name="ix_occurrences_repository_version",
        ),
        IndexModel([("gene_id", ASCENDING)], name="ix_occurrences_gene"),
        IndexModel([("relative_path", ASCENDING)], name="ix_occurrences_relative_path"),
    ),
    "gene_statistics": (
        IndexModel([("statistics_id", ASCENDING)], unique=True, name="uq_statistics_id"),
        IndexModel([("project_count", DESCENDING)], name="ix_statistics_project_count"),
        IndexModel([("version_count", DESCENDING)], name="ix_statistics_version_count"),
    ),
    "evolution_edges": (
        IndexModel([("evolution_edge_id", ASCENDING)], unique=True, name="uq_evolution_edge_id"),
        IndexModel([("source_gene_ids", ASCENDING)], name="ix_edges_source_gene"),
        IndexModel([("target_gene_ids", ASCENDING)], name="ix_edges_target_gene"),
    ),
    "gene_families": (IndexModel([("family_id", ASCENDING)], unique=True, name="uq_family_id"),),
    "family_members": (
        IndexModel(
            [("family_id", ASCENDING), ("gene_id", ASCENDING)],
            unique=True,
            name="uq_family_member",
        ),
        IndexModel([("gene_id", ASCENDING)], name="ix_family_members_gene"),
    ),
    "pipeline_runs": (
        IndexModel([("pipeline_run_id", ASCENDING)], unique=True, name="uq_pipeline_run_id"),
        IndexModel([("repository_id", ASCENDING), ("status", ASCENDING)], name="ix_runs_scope"),
    ),
    "processing_failures": (
        IndexModel([("failure_id", ASCENDING)], unique=True, name="uq_failure_id"),
        IndexModel(
            [("pipeline_run_id", ASCENDING), ("stage", ASCENDING)],
            name="ix_failures_run_stage",
        ),
        IndexModel(
            [("target_kind", ASCENDING), ("target_id", ASCENDING)],
            name="ix_failures_target",
        ),
    ),
}
