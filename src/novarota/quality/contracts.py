"""Tipos e dominios Silver; campos nao listados mantem tipo STRING."""

from novarota.contracts import SOURCES

TYPES = {
    "renda": "DECIMAL(18,2)", "limite": "DECIMAL(18,2)",
    "valor": "DECIMAL(18,2)", "valor_estorno": "DECIMAL(18,2)",
    "sequencia_origem": "BIGINT", "data_abertura": "DATE",
    **{name: "TIMESTAMP" for name in (
        "data_atualizacao", "data_transacao", "data_evento", "data_estorno")},
}
ENUMS = {
    "operacao": ("I", "U", "D"),
    "status_conta": ("ATIVA", "ENCERRADA"),
    "tipo_conta": ("CORRENTE", "POUPANCA", "PAGAMENTO"),
    "tipo_cartao": ("CREDITO", "DEBITO", "MULTIPLO"),
    "status_cartao": ("ATIVO", "CANCELADO"),
    "status_transacao": ("APROVADA", "PENDENTE", "CANCELADA"),
    "tipo_evento": ("SUSPEITA", "FRAUDE", "CHARGEBACK"),
    "severidade": ("BAIXA", "MEDIA", "ALTA", "CRITICA"),
}
ENTITIES = {"clientes_cdc": "id_cliente", "contas_cdc": "id_conta", "cartoes_cdc": "id_cartao"}
EVENT_TABLES = {"clientes_cdc": "clientes_eventos", "contas_cdc": "contas_eventos", "cartoes_cdc": "cartoes_eventos"}
HISTORY_TABLES = {"clientes_cdc": "clientes_scd2", "contas_cdc": "contas_scd2", "cartoes_cdc": "cartoes_scd2"}
TIMESTAMPS = {
    **{source: "data_atualizacao" for source in ENTITIES},
    "transacoes": "data_transacao", "eventos_risco": "data_evento", "estornos": "data_estorno",
}


def identity_fields(source: str) -> tuple[str, ...]:
    return ("id_transacao", "sequencia_origem") if source == "transacoes" else (SOURCES[source].key,)


def typed_fields(source: str) -> dict[str, str]:
    return {name: TYPES.get(name, "STRING") for name in SOURCES[source].fields}
