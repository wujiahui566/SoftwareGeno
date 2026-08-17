"""Regression and invariance tests for identifier scheme version 1."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from geno.identity import (
    CandidateUnitId,
    GeneId,
    RepositoryId,
    SourceFileId,
    canonical_json_bytes,
    create_candidate_unit_id,
    create_evolution_edge_id,
    create_family_id,
    create_gene_id,
    create_local_repository_id,
    create_normalized_unit_id,
    create_occurrence_id,
    create_pipeline_run_id,
    create_repository_id,
    create_source_file_id,
    create_version_id,
    normalize_relative_path,
)
from geno.identity.identifiers import _create_identifier

COMMIT_ONE = "0123456789abcdef0123456789abcdef01234567"
COMMIT_TWO = "fedcba9876543210fedcba9876543210fedcba98"
NORMALIZED_CORE = "int fn(int p0){int v0=p0+<int>;return v0;}"


@dataclass(frozen=True)
class RepositoryMetadata:
    git_url: str
    owner: str
    name: str
    stars: int
    description: str


def test_identical_inputs_produce_identical_ids() -> None:
    first = _identity_graph()
    second = _identity_graph()

    assert first == second


def test_identifier_prefixes_and_golden_vectors() -> None:
    graph = _identity_graph()

    assert graph == {
        # Scheme-version 1 compatibility vectors; change only with a new ADR and scheme version.
        "repository_id": "repo_1324941cbfb6d717bc693b702a9df6ce21d181872229528e96083b3a19ec9dc1",
        "version_id": "ver_9561be658533304eb92152aba4ae136d16acb784285dcc2db146520f0333eebb",
        "source_file_id": "file_5e30824dff607a4d6b59c775eb60c252e28b4a70aee994566f575f4ce948d613",
        "candidate_unit_id": (
            "unit_ae2ccc5113261afd8f2b71df9dbf05fad4d1986053433acc61e0e87ca5e10ad6"
        ),
        "normalized_unit_id": (
            "norm_204dbc73f5c0c3ff682bd744e7666cc50bcd96ceae6e08fca51d0f81afaab49d"
        ),
        "gene_id": "gene_0f9c78476a24956e6141977b1ed375d08e60b56404e5286509db2d2380113384",
        "occurrence_id": "occ_40ad9a209fe614fb246822ac5c971c646342a84b2be88ef80a43062b32dc9347",
        "evolution_edge_id": (
            "edge_8a7c57b8aef37596dd822664a4ab8530ae144a84ef3ded35b9c1a30f33811f0f"
        ),
        "family_id": "fam_c557909247060e0b5fb3a4c4eeed2ec99363370c2e6db501aa79b5f4b2b69ff4",
        "pipeline_run_id": "run_91042fbae81a283414c9ae6f636e7c5105c281dc6db93c1ab6a0a48297cabbbd",
    }


def test_local_repository_v2_golden_vector() -> None:
    assert create_local_repository_id(canonical_path="/srv/geno/repositories/example") == (
        "repo_6b644d1b138c333f0adc05cb02ccc9bcbc3083e1b4de99a194f601b902370d2f"
    )


def test_dictionary_order_does_not_affect_ids() -> None:
    first = {"host": "example.com", "metadata": {"b": "two", "a": "one"}}
    second = {"metadata": {"a": "one", "b": "two"}, "host": "example.com"}

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert _create_identifier("order_fixture", "repo_", first) == _create_identifier(
        "order_fixture", "repo_", second
    )


def test_unicode_composition_does_not_affect_serialization_or_repository_id() -> None:
    composed = "caf\u00e9"
    decomposed = "cafe\u0301"

    assert canonical_json_bytes({"owner": composed}) == canonical_json_bytes({"owner": decomposed})
    assert create_repository_id(
        "https://example.com/caf%C3%A9/geno.git", owner=composed, name="geno"
    ) == create_repository_id(
        "git@example.com:cafe%CC%81/geno.git", owner=decomposed, name="GENO.git"
    )


def test_git_transport_owner_and_name_forms_normalize_to_same_repository_id() -> None:
    https_id = create_repository_id(
        "https://GitHub.COM:443/OpenAI/Geno.git", owner="OpenAI", name="Geno.git"
    )
    ssh_id = create_repository_id("git@github.com:openai/geno.git", owner="openai", name="geno")

    assert https_id == ssh_id


def test_mutable_repository_metadata_does_not_change_repository_id() -> None:
    original = RepositoryMetadata(
        git_url="https://github.com/openai/geno.git",
        owner="openai",
        name="geno",
        stars=10,
        description="first description",
    )
    changed = replace(original, stars=100_000, description="new description")

    assert _repository_id_from_metadata(original) == _repository_id_from_metadata(changed)


def test_windows_and_posix_paths_produce_same_source_file_id() -> None:
    repository_id = _repository_id()
    version_id = create_version_id(repository_id, commit_hash=COMMIT_ONE)

    windows_id = create_source_file_id(version_id, relative_path=r"src\core\.\gene.cpp")
    posix_id = create_source_file_id(version_id, relative_path="src/core/gene.cpp")

    assert windows_id == posix_id
    assert normalize_relative_path(r"src\core\.\gene.cpp") == "src/core/gene.cpp"


def test_changing_context_does_not_change_gene_id() -> None:
    gene_id = _gene_id()
    repository_id = _repository_id()
    version_id = create_version_id(repository_id, commit_hash=COMMIT_ONE)
    first_file_id = create_source_file_id(version_id, relative_path="src/first.cpp")
    second_file_id = create_source_file_id(version_id, relative_path="moved/second.cpp")
    first_unit_id = _candidate_id(first_file_id, start_byte=10)
    second_unit_id = _candidate_id(second_file_id, start_byte=200)

    assert gene_id == _gene_id()
    assert create_occurrence_id(gene_id, candidate_unit_id=first_unit_id) != create_occurrence_id(
        gene_id, candidate_unit_id=second_unit_id
    )


def test_changing_normalized_core_code_changes_gene_id() -> None:
    original = _gene_id()
    changed = create_gene_id(
        language="cpp",
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        normalized_core_code="int fn(int p0){int v0=p0-<int>;return v0;}",
    )

    assert original != changed


def test_local_rename_after_normalization_does_not_change_gene_id() -> None:
    raw_before = "int add(int value) { int result = value + 1; return result; }"
    raw_after = "int add(int input) { int output = input + 1; return output; }"
    normalized_before = NORMALIZED_CORE
    normalized_after = NORMALIZED_CORE

    assert raw_before != raw_after
    assert create_gene_id(
        language="cpp",
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        normalized_core_code=normalized_before,
    ) == create_gene_id(
        language="cpp",
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        normalized_core_code=normalized_after,
    )


def test_set_like_members_are_order_independent() -> None:
    repository_id = _repository_id()
    first_version = create_version_id(repository_id, commit_hash=COMMIT_ONE)
    second_version = create_version_id(repository_id, commit_hash=COMMIT_TWO)
    gene_one = _gene_id()
    gene_two = create_gene_id(
        language="cpp",
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        normalized_core_code="void fn(){return;}",
    )

    assert create_family_id(
        gene_ids=[gene_one, gene_two],
        algorithm="connected-components",
        algorithm_version="1",
        configuration_version="families-v1",
    ) == create_family_id(
        gene_ids=[gene_two, gene_one],
        algorithm="connected-components",
        algorithm_version="1",
        configuration_version="families-v1",
    )
    assert create_pipeline_run_id(
        repository_id=repository_id,
        version_ids=[first_version, second_version],
        pipeline_version="0.1.0",
        configuration_id="config_fixture_v1",
        idempotency_key="fixture-run",
    ) == create_pipeline_run_id(
        repository_id=repository_id,
        version_ids=[second_version, first_version],
        pipeline_version="0.1.0",
        configuration_id="config_fixture_v1",
        idempotency_key="fixture-run",
    )


def test_invalid_paths_and_floating_point_envelopes_are_rejected() -> None:
    with pytest.raises(ValueError, match="traverse"):
        normalize_relative_path("../outside.cpp")
    with pytest.raises(TypeError, match="floating-point"):
        canonical_json_bytes({"score": 0.5})


def _identity_graph() -> dict[str, str]:
    repository_id = _repository_id()
    version_id = create_version_id(repository_id, commit_hash=COMMIT_ONE)
    next_version_id = create_version_id(repository_id, commit_hash=COMMIT_TWO)
    source_file_id = create_source_file_id(version_id, relative_path="src/gene.cpp")
    candidate_unit_id = _candidate_id(source_file_id, start_byte=10)
    normalized_unit_id = create_normalized_unit_id(
        candidate_unit_id,
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        configuration_version="normalization-v1",
    )
    gene_id = _gene_id()
    occurrence_id = create_occurrence_id(gene_id, candidate_unit_id=candidate_unit_id)
    target_file_id = create_source_file_id(next_version_id, relative_path="src/gene.cpp")
    target_unit_id = _candidate_id(target_file_id, start_byte=20)
    target_occurrence_id = create_occurrence_id(gene_id, candidate_unit_id=target_unit_id)
    evolution_edge_id = create_evolution_edge_id(
        repository_id=repository_id,
        from_version_id=version_id,
        to_version_id=next_version_id,
        relation_type="retention",
        source_occurrence_ids=[occurrence_id],
        target_occurrence_ids=[target_occurrence_id],
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
        idempotency_key="fixture-run",
    )
    return {
        "repository_id": repository_id,
        "version_id": version_id,
        "source_file_id": source_file_id,
        "candidate_unit_id": candidate_unit_id,
        "normalized_unit_id": normalized_unit_id,
        "gene_id": gene_id,
        "occurrence_id": occurrence_id,
        "evolution_edge_id": evolution_edge_id,
        "family_id": family_id,
        "pipeline_run_id": pipeline_run_id,
    }


def _repository_id() -> RepositoryId:
    return create_repository_id(
        "https://github.com/OpenAI/Geno.git",
        owner="OpenAI",
        name="Geno",
    )


def _repository_id_from_metadata(metadata: RepositoryMetadata) -> RepositoryId:
    return create_repository_id(
        metadata.git_url,
        owner=metadata.owner,
        name=metadata.name,
    )


def _candidate_id(source_file_id: SourceFileId, *, start_byte: int) -> CandidateUnitId:
    return create_candidate_unit_id(
        source_file_id,
        analyzer="clang-adapter",
        analyzer_version="1",
        unit_kind="function",
        start_byte=start_byte,
        end_byte=start_byte + 80,
    )


def _gene_id() -> GeneId:
    return create_gene_id(
        language="cpp",
        normalization_algorithm="cpp-token-normalizer",
        normalization_version="1",
        normalized_core_code=NORMALIZED_CORE,
    )
