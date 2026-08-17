"""Unit tests for every explicit MongoDB record codec."""

from __future__ import annotations

from typing import Any

import pytest

from geno.domain import DomainRecord
from geno.storage import PersistenceDataError
from geno.storage.mongodb.codecs import (
    CANDIDATE_UNIT_CODEC,
    EVOLUTION_EDGE_CODEC,
    FAMILY_MEMBER_CODEC,
    GENE_CODEC,
    GENE_FAMILY_CODEC,
    GENE_FEATURE_CODEC,
    GENE_OCCURRENCE_CODEC,
    GENE_STATISTICS_CODEC,
    NORMALIZED_UNIT_CODEC,
    PIPELINE_RUN_CODEC,
    PROCESSING_FAILURE_CODEC,
    REPOSITORY_CODEC,
    SOURCE_FILE_CODEC,
    VERSION_CODEC,
    RecordCodec,
)
from tests.factories import persistence_records

RECORDS = persistence_records()
CODECS: tuple[RecordCodec[Any], ...] = (
    REPOSITORY_CODEC,
    VERSION_CODEC,
    SOURCE_FILE_CODEC,
    CANDIDATE_UNIT_CODEC,
    NORMALIZED_UNIT_CODEC,
    GENE_FEATURE_CODEC,
    GENE_CODEC,
    GENE_OCCURRENCE_CODEC,
    GENE_STATISTICS_CODEC,
    EVOLUTION_EDGE_CODEC,
    GENE_FAMILY_CODEC,
    FAMILY_MEMBER_CODEC,
    PIPELINE_RUN_CODEC,
    PROCESSING_FAILURE_CODEC,
)


@pytest.mark.parametrize(("record", "codec"), zip(RECORDS, CODECS, strict=True))
def test_explicit_codec_round_trip(record: DomainRecord, codec: RecordCodec[Any]) -> None:
    document = codec.serialize(record)

    assert isinstance(document["_id"], str)
    assert codec.deserialize(document) == record


def test_deserializer_rejects_storage_id_mismatch() -> None:
    document = REPOSITORY_CODEC.serialize(RECORDS[0])
    document["_id"] = "repo_corrupt"

    with pytest.raises(PersistenceDataError, match="does not match"):
        REPOSITORY_CODEC.deserialize(document)


def test_family_member_codec_uses_pair_key() -> None:
    family_member = RECORDS[11]

    loaded = FAMILY_MEMBER_CODEC.deserialize(FAMILY_MEMBER_CODEC.serialize(family_member))

    assert loaded == family_member
    assert FAMILY_MEMBER_CODEC.storage_id_from_key(
        (str(family_member.family_id), str(family_member.gene_id))
    ).startswith("fam_")
