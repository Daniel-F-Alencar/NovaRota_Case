"""Verificacoes de transformacao para executar no Spark real do Databricks."""

from dataclasses import replace
import json

from novarota.config import PipelineConfig
from novarota.contracts import SourceContract
from novarota.ingestion.bronze import enrich_bronze
from novarota.ingestion.hashing import row_hash


def verify_transformations(spark, config: PipelineConfig) -> dict:
    contract = SourceContract("probe", "json", ("id", "valor"), "id")
    origin = "/Volumes/test/ops/files/landing/probe/batch_probe/schema_v1/probe.json"
    records = [
        ("same_a", "A", "10.00", '{"dispositivo":"app","_file_path":"/first"}', None, origin),
        ("same_b", "A", "10.00", '{"dispositivo":"app","_file_path":"/second"}', None, origin + ".copy"),
        ("changed", "A", "10.00", '{"dispositivo":"web","_file_path":"/first"}', None, origin),
        ("null", "U", None, None, None, origin),
        ("empty", "U", "", None, None, origin),
        ("unicode", "São Paulo", '"\\\n', None, None, origin),
        ("corrupt", "C", None, None, "broken{", origin),
    ]
    schema = "case_id string, id string, valor string, _rescued_data string, _corrupt_record string, arquivo_origem string"
    frame = spark.createDataFrame(records, schema=schema)
    actual = {row["case_id"]: row.asDict() for row in enrich_bronze(frame, contract, config).collect()}
    for case_id, identity, value, rescue, corrupt, _ in records:
        payload = {"id": identity, "valor": value}
        payload.update({k: v for k, v in json.loads(rescue or "{}").items() if k != "_file_path"})
        row = actual[case_id]
        if row["hash_linha"] != row_hash(payload, contract, corrupt):
            raise AssertionError(f"Hash Spark difere do oracle Python em {case_id}")
        if row["batch_id"] != "batch_probe" or row["schema_version"] != "1" or row["run_id"] != config.run_id:
            raise AssertionError(f"Metadados inconsistentes em {case_id}")
    if actual["same_a"]["hash_linha"] != actual["same_b"]["hash_linha"]:
        raise AssertionError("Caminho do rescue alterou hash")
    if actual["same_a"]["hash_linha"] == actual["changed"]["hash_linha"]:
        raise AssertionError("Campo resgatado nao contribui para hash")
    if actual["null"]["hash_linha"] == actual["empty"]["hash_linha"]:
        raise AssertionError("String vazia e null foram confundidos")
    retried = {row["case_id"]: row["hash_linha"] for row in enrich_bronze(frame, contract, replace(config, run_id="different_attempt")).collect()}
    if retried != {case_id: row["hash_linha"] for case_id, row in actual.items()}:
        raise AssertionError("Metadados da tentativa alteraram hash de payload")
    return {"status": "PASSED", "rows": len(records), "checks": ["canonical_hash", "rescue_path_excluded", "rescued_value_included", "null_vs_empty", "unicode", "corrupt_payload", "metadata", "attempt_independent_hash"]}
