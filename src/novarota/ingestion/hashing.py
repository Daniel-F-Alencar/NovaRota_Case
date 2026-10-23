"""Representacao canonica documentada para payloads planos da origem."""

from hashlib import sha256
import json

from novarota.contracts import SourceContract


def canonical_payload(payload: dict, contract: SourceContract, corrupt_record: str | None = None) -> str:
    values = {name: payload.get(name) for name in contract.fields}
    values.update(payload)
    if corrupt_record is not None:
        values["_corrupt_record"] = corrupt_record
    for key, value in values.items():
        if not isinstance(key, str) or (value is not None and not isinstance(value, str)):
            raise ValueError("Payload canonico exige valores string ou null")
    return json.dumps([{"key": key, "value": values[key]} for key in sorted(values)],
                      ensure_ascii=False, separators=(",", ":"))


def row_hash(payload: dict, contract: SourceContract, corrupt_record: str | None = None) -> str:
    return sha256(canonical_payload(payload, contract, corrupt_record).encode("utf-8")).hexdigest()
