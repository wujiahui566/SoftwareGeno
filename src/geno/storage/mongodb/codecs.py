"""Explicit BSON serializers and deserializers for Geno persistence records."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ValidationError

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
from geno.storage.errors import PersistenceDataError
from geno.storage.protocols import RecordKey

type Document = dict[str, Any]


@dataclass(frozen=True, slots=True)
class RecordCodec[RecordT]:
    """Collection-specific conversion and storage-key behavior."""

    serialize: Callable[[RecordT], Document]
    deserialize: Callable[[Mapping[str, Any]], RecordT]
    storage_id_from_key: Callable[[RecordKey], str]


def serialize_repository(record: RepositoryRecord) -> Document:
    return _serialize_record(record, str(record.repository_id))


def deserialize_repository(document: Mapping[str, Any]) -> RepositoryRecord:
    return _deserialize_record(RepositoryRecord, document, "repository_id")


def serialize_version(record: VersionRecord) -> Document:
    return _serialize_record(record, str(record.version_id))


def deserialize_version(document: Mapping[str, Any]) -> VersionRecord:
    return _deserialize_record(VersionRecord, document, "version_id")


def serialize_source_file(record: SourceFileRecord) -> Document:
    return _serialize_record(record, str(record.source_file_id))


def deserialize_source_file(document: Mapping[str, Any]) -> SourceFileRecord:
    return _deserialize_record(SourceFileRecord, document, "source_file_id")


def serialize_candidate_unit(record: CandidateUnitRecord) -> Document:
    return _serialize_record(record, str(record.candidate_unit_id))


def deserialize_candidate_unit(document: Mapping[str, Any]) -> CandidateUnitRecord:
    return _deserialize_record(CandidateUnitRecord, document, "candidate_unit_id")


def serialize_normalized_unit(record: NormalizedUnitRecord) -> Document:
    return _serialize_record(record, str(record.normalized_unit_id))


def deserialize_normalized_unit(document: Mapping[str, Any]) -> NormalizedUnitRecord:
    return _deserialize_record(NormalizedUnitRecord, document, "normalized_unit_id")


def serialize_gene_feature(record: GeneFeatureRecord) -> Document:
    return _serialize_record(record, record.feature_set_id)


def deserialize_gene_feature(document: Mapping[str, Any]) -> GeneFeatureRecord:
    return _deserialize_record(GeneFeatureRecord, document, "feature_set_id")


def serialize_gene(record: GeneRecord) -> Document:
    return _serialize_record(record, str(record.gene_id))


def deserialize_gene(document: Mapping[str, Any]) -> GeneRecord:
    return _deserialize_record(GeneRecord, document, "gene_id")


def serialize_gene_occurrence(record: GeneOccurrenceRecord) -> Document:
    return _serialize_record(record, str(record.occurrence_id))


def deserialize_gene_occurrence(document: Mapping[str, Any]) -> GeneOccurrenceRecord:
    return _deserialize_record(GeneOccurrenceRecord, document, "occurrence_id")


def serialize_gene_statistics(record: GeneStatisticsRecord) -> Document:
    return _serialize_record(record, record.statistics_id)


def deserialize_gene_statistics(document: Mapping[str, Any]) -> GeneStatisticsRecord:
    return _deserialize_record(GeneStatisticsRecord, document, "statistics_id")


def serialize_evolution_edge(record: EvolutionEdgeRecord) -> Document:
    return _serialize_record(record, str(record.evolution_edge_id))


def deserialize_evolution_edge(document: Mapping[str, Any]) -> EvolutionEdgeRecord:
    return _deserialize_record(EvolutionEdgeRecord, document, "evolution_edge_id")


def serialize_gene_family(record: GeneFamilyRecord) -> Document:
    return _serialize_record(record, str(record.family_id))


def deserialize_gene_family(document: Mapping[str, Any]) -> GeneFamilyRecord:
    return _deserialize_record(GeneFamilyRecord, document, "family_id")


def serialize_family_member(record: FamilyMemberRecord) -> Document:
    return _serialize_record(record, _family_member_storage_id(record.family_id, record.gene_id))


def deserialize_family_member(document: Mapping[str, Any]) -> FamilyMemberRecord:
    record = _deserialize_record(FamilyMemberRecord, document)
    expected_storage_id = _family_member_storage_id(record.family_id, record.gene_id)
    _validate_storage_id(document, expected_storage_id)
    return record


def serialize_pipeline_run(record: PipelineRunRecord) -> Document:
    return _serialize_record(record, str(record.pipeline_run_id))


def deserialize_pipeline_run(document: Mapping[str, Any]) -> PipelineRunRecord:
    return _deserialize_record(PipelineRunRecord, document, "pipeline_run_id")


def serialize_processing_failure(record: ProcessingFailureRecord) -> Document:
    return _serialize_record(record, record.failure_id)


def deserialize_processing_failure(document: Mapping[str, Any]) -> ProcessingFailureRecord:
    return _deserialize_record(ProcessingFailureRecord, document, "failure_id")


def _single_storage_id(key: RecordKey) -> str:
    if not isinstance(key, str) or not key:
        msg = "record key must be a non-empty string"
        raise ValueError(msg)
    return key


def _family_member_key_storage_id(key: RecordKey) -> str:
    if not isinstance(key, tuple) or len(key) != 2:
        msg = "family member key must be a (family_id, gene_id) pair"
        raise ValueError(msg)
    return _family_member_storage_id(key[0], key[1])


def _family_member_storage_id(family_id: object, gene_id: object) -> str:
    return f"{family_id}|{gene_id}"


REPOSITORY_CODEC = RecordCodec(
    serialize=serialize_repository,
    deserialize=deserialize_repository,
    storage_id_from_key=_single_storage_id,
)
VERSION_CODEC = RecordCodec(
    serialize=serialize_version,
    deserialize=deserialize_version,
    storage_id_from_key=_single_storage_id,
)
SOURCE_FILE_CODEC = RecordCodec(
    serialize=serialize_source_file,
    deserialize=deserialize_source_file,
    storage_id_from_key=_single_storage_id,
)
CANDIDATE_UNIT_CODEC = RecordCodec(
    serialize=serialize_candidate_unit,
    deserialize=deserialize_candidate_unit,
    storage_id_from_key=_single_storage_id,
)
NORMALIZED_UNIT_CODEC = RecordCodec(
    serialize=serialize_normalized_unit,
    deserialize=deserialize_normalized_unit,
    storage_id_from_key=_single_storage_id,
)
GENE_FEATURE_CODEC = RecordCodec(
    serialize=serialize_gene_feature,
    deserialize=deserialize_gene_feature,
    storage_id_from_key=_single_storage_id,
)
GENE_CODEC = RecordCodec(
    serialize=serialize_gene,
    deserialize=deserialize_gene,
    storage_id_from_key=_single_storage_id,
)
GENE_OCCURRENCE_CODEC = RecordCodec(
    serialize=serialize_gene_occurrence,
    deserialize=deserialize_gene_occurrence,
    storage_id_from_key=_single_storage_id,
)
GENE_STATISTICS_CODEC = RecordCodec(
    serialize=serialize_gene_statistics,
    deserialize=deserialize_gene_statistics,
    storage_id_from_key=_single_storage_id,
)
EVOLUTION_EDGE_CODEC = RecordCodec(
    serialize=serialize_evolution_edge,
    deserialize=deserialize_evolution_edge,
    storage_id_from_key=_single_storage_id,
)
GENE_FAMILY_CODEC = RecordCodec(
    serialize=serialize_gene_family,
    deserialize=deserialize_gene_family,
    storage_id_from_key=_single_storage_id,
)
FAMILY_MEMBER_CODEC = RecordCodec(
    serialize=serialize_family_member,
    deserialize=deserialize_family_member,
    storage_id_from_key=_family_member_key_storage_id,
)
PIPELINE_RUN_CODEC = RecordCodec(
    serialize=serialize_pipeline_run,
    deserialize=deserialize_pipeline_run,
    storage_id_from_key=_single_storage_id,
)
PROCESSING_FAILURE_CODEC = RecordCodec(
    serialize=serialize_processing_failure,
    deserialize=deserialize_processing_failure,
    storage_id_from_key=_single_storage_id,
)


def _serialize_record(record: BaseModel, storage_id: str) -> Document:
    payload = cast(Document, _to_bson_value(record.model_dump(mode="python")))
    return {"_id": storage_id, **payload}


def _deserialize_record[RecordT: BaseModel](
    model: type[RecordT],
    document: Mapping[str, Any],
    identity_field: str | None = None,
) -> RecordT:
    payload = {key: value for key, value in document.items() if key != "_id"}
    try:
        record = model.model_validate(payload)
    except ValidationError as error:
        msg = f"invalid {model.__name__} document: {error}"
        raise PersistenceDataError(msg) from error
    if identity_field is not None:
        _validate_storage_id(document, str(getattr(record, identity_field)))
    return record


def _validate_storage_id(document: Mapping[str, Any], expected: str) -> None:
    if document.get("_id") != expected:
        msg = f"storage _id does not match domain identity: {document.get('_id')!r} != {expected!r}"
        raise PersistenceDataError(msg)


def _to_bson_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool, datetime)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _to_bson_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_bson_value(item) for item in value]
    msg = f"unsupported BSON record value: {type(value).__name__}"
    raise PersistenceDataError(msg)
