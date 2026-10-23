"""Campos lexicais da origem; tipagem financeira pertence a Prata."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceContract:
    name: str
    format: str
    fields: tuple[str, ...]
    key: str


_CDC = ("data_atualizacao", "operacao", "id_evento_cdc", "sequencia_origem")
SOURCES = {
    source.name: source
    for source in (
        SourceContract("clientes_cdc", "json", ("id_cliente", "cpf", "nome", "cidade", "estado", "renda", "segmento") + _CDC, "id_evento_cdc"),
        SourceContract("contas_cdc", "json", ("id_conta", "id_cliente", "tipo_conta", "status_conta", "data_abertura") + _CDC, "id_evento_cdc"),
        SourceContract("cartoes_cdc", "json", ("id_cartao", "id_conta", "tipo_cartao", "limite", "status_cartao") + _CDC, "id_evento_cdc"),
        SourceContract("transacoes", "csv", ("id_transacao", "id_cartao", "data_transacao", "valor", "mcc", "estabelecimento", "canal", "pais", "moeda", "id_estabelecimento", "status_transacao", "data_atualizacao", "sequencia_origem"), "id_transacao"),
        SourceContract("eventos_risco", "csv", ("id_evento", "id_transacao", "tipo_evento", "severidade", "data_evento"), "id_evento"),
        SourceContract("estornos", "csv", ("id_estorno", "id_transacao", "data_estorno", "motivo", "valor_estorno", "moeda"), "id_estorno"),
    )
}
