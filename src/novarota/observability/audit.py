from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from typing import Iterator, Protocol
from uuid import uuid4

from novarota.config import PipelineConfig

LOGGER = logging.getLogger("novarota")
AUDIT_SCHEMA = "event_id string, run_id string, batch_id string, source string, status string, event_at timestamp, metrics_json string, error_message string"


class EventWriter(Protocol):
    def emit(self, source: str, status: str, metrics: dict, error: str | None = None) -> None: ...


@dataclass
class DeltaAuditWriter:
    spark: object
    config: PipelineConfig

    def emit(self, source: str, status: str, metrics: dict, error: str | None = None) -> None:
        payload = (uuid4().hex, self.config.run_id, self.config.batch_id, source, status,
                   datetime.now(timezone.utc), json.dumps(metrics, sort_keys=True), error)
        table = f"{self.config.catalog}.{self.config.ops_schema}.pipeline_events"
        self.spark.createDataFrame([payload], schema=AUDIT_SCHEMA).write.format("delta").mode("append").saveAsTable(table)
        LOGGER.info(json.dumps({"run_id": self.config.run_id, "batch_id": self.config.batch_id,
                                "source": source, "status": status, "metrics": metrics, "error": error}, ensure_ascii=False))


@contextmanager
def audited(writer: EventWriter, source: str) -> Iterator[dict]:
    """Falha na auditoria de erro nao substitui a excecao original."""
    metrics = {}
    writer.emit(source, "STARTED", metrics)
    try:
        yield metrics
    except Exception as error:
        LOGGER.exception("Falha na etapa %s", source)
        try:
            writer.emit(source, "FAILED", metrics, f"{type(error).__name__}: {error}"[:4000])
        except Exception:
            LOGGER.exception("Nao foi possivel persistir o evento FAILED de %s", source)
        raise
    else:
        # Falha ao registrar SUCCEEDED tambem deve interromper o chamador.
        writer.emit(source, "SUCCEEDED", metrics)
