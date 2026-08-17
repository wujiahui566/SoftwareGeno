"""Docker-backed integration tests for the MongoDB persistence adapter."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from pymongo import MongoClient
from pymongo.database import Database
from typer.testing import CliRunner

from geno.cli.app import app
from geno.domain import RepositoryRecord
from geno.identity import RepositoryId
from geno.storage.mongodb import MongoPersistence
from geno.storage.mongodb.codecs import Document
from geno.storage.mongodb.indexes import COLLECTION_NAMES
from geno.storage.protocols import RecordRepository
from tests.factories import persistence_records

pytestmark = pytest.mark.integration

DATABASE_NAME = "geno_integration_persistence"
MONGODB_URI = os.environ.get("GENO_TEST_MONGODB_URI", "mongodb://localhost:27017")


@dataclass(frozen=True)
class MongoFixture:
    persistence: MongoPersistence
    database: Database[Document]


@pytest.fixture(scope="module")
def mongo() -> Iterator[MongoFixture]:
    client: MongoClient[Document] = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=5_000,
        tz_aware=True,
    )
    client.admin.command("ping")
    client.drop_database(DATABASE_NAME)
    persistence = MongoPersistence(MONGODB_URI, DATABASE_NAME)
    try:
        yield MongoFixture(persistence=persistence, database=client[DATABASE_NAME])
    finally:
        persistence.close()
        client.drop_database(DATABASE_NAME)
        client.close()


def test_initialize_health_and_required_indexes(mongo: MongoFixture) -> None:
    first = mongo.persistence.initialize()
    second = mongo.persistence.initialize()
    health = mongo.persistence.health_check()

    assert first.collection_count == len(COLLECTION_NAMES)
    assert second.collection_count == len(COLLECTION_NAMES)
    assert set(mongo.database.list_collection_names()) == set(COLLECTION_NAMES)
    assert health.healthy is True
    assert health.server_version is not None

    expected_indexes = {
        "versions": {"uq_version_id", "ix_versions_repository_commit_time"},
        "gene_occurrences": {
            "uq_occurrence_id",
            "ix_occurrences_repository_version",
            "ix_occurrences_gene",
            "ix_occurrences_relative_path",
        },
        "gene_statistics": {
            "ix_statistics_project_count",
            "ix_statistics_version_count",
        },
        "evolution_edges": {"ix_edges_source_gene", "ix_edges_target_gene"},
        "family_members": {"uq_family_member"},
    }
    for collection_name, index_names in expected_indexes.items():
        assert index_names <= set(mongo.database[collection_name].index_information())


def test_all_repositories_upsert_and_deserialize_idempotently(mongo: MongoFixture) -> None:
    records = persistence_records()
    _assert_idempotent_upsert(mongo.persistence.repositories, records[0])
    _assert_idempotent_upsert(mongo.persistence.versions, records[1])
    _assert_idempotent_upsert(mongo.persistence.source_files, records[2])
    _assert_idempotent_upsert(mongo.persistence.candidate_units, records[3])
    _assert_idempotent_upsert(mongo.persistence.normalized_units, records[4])
    _assert_idempotent_upsert(mongo.persistence.gene_features, records[5])
    _assert_idempotent_upsert(mongo.persistence.genes, records[6])
    _assert_idempotent_upsert(mongo.persistence.gene_occurrences, records[7])
    _assert_idempotent_upsert(mongo.persistence.gene_statistics, records[8])
    _assert_idempotent_upsert(mongo.persistence.evolution_edges, records[9])
    _assert_idempotent_upsert(mongo.persistence.gene_families, records[10])
    _assert_idempotent_upsert(mongo.persistence.family_members, records[11])
    _assert_idempotent_upsert(mongo.persistence.pipeline_runs, records[12])
    _assert_idempotent_upsert(mongo.persistence.processing_failures, records[13])

    assert all(mongo.database[name].count_documents({}) == 1 for name in COLLECTION_NAMES)
    assert mongo.persistence.repositories.get(str(records[0].repository_id)) == records[0]
    assert (
        mongo.persistence.family_members.get((str(records[11].family_id), str(records[11].gene_id)))
        == records[11]
    )


def test_bulk_upsert_pagination_and_statistics(mongo: MongoFixture) -> None:
    base = persistence_records()[0]
    records: list[RepositoryRecord] = [
        base.model_copy(
            update={
                "repository_id": RepositoryId(f"repo_{index:064x}"),
                "canonical_locator": f"example.com/geno/{index}",
                "name": f"geno-{index}",
            }
        )
        for index in range(3)
    ]

    first_bulk = mongo.persistence.repositories.bulk_upsert(records)
    second_bulk = mongo.persistence.repositories.bulk_upsert(records)
    first_page = mongo.persistence.repositories.page(limit=2)
    second_page = mongo.persistence.repositories.page(after=first_page.next_cursor, limit=2)
    statistics = mongo.persistence.statistics()

    assert first_bulk.created_count == 3
    assert second_bulk.created_count == 0
    assert second_bulk.modified_count == 0
    assert len(first_page.items) == 2
    assert first_page.next_cursor is not None
    assert len(second_page.items) == 2
    assert statistics.collection_counts["repositories"] == 4
    assert statistics.total_documents == len(COLLECTION_NAMES) + 3


def test_database_cli_commands_against_mongodb(mongo: MongoFixture) -> None:
    runner = CliRunner()
    environment = {
        "GENO_MONGODB_URI": MONGODB_URI,
        "GENO_MONGODB_DATABASE": DATABASE_NAME,
    }

    init_result = runner.invoke(app, ["database", "init"], env=environment)
    check_result = runner.invoke(app, ["database", "check"], env=environment)
    stats_result = runner.invoke(app, ["database", "stats"], env=environment)

    assert init_result.exit_code == 0
    assert check_result.exit_code == 0
    assert stats_result.exit_code == 0
    assert json.loads(check_result.stdout)["healthy"] is True
    assert json.loads(stats_result.stdout)["collection_counts"]["repositories"] == 4


def _assert_idempotent_upsert[RecordT](
    repository: RecordRepository[RecordT], record: RecordT
) -> None:
    first = repository.upsert(record)
    second = repository.upsert(record)
    assert first.created is True
    assert second.created is False
    assert second.modified_count == 0
