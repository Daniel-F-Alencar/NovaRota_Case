"""Cenarios pequenos identificaveis, independentes do volume aleatorio."""

from datetime import date, timedelta

from novarota.contracts import SOURCES

BATCH_IDS = (
    "batch_001_initial", "batch_002_incremental",
    "batch_003_late", "batch_004_schema",
)


def synthetic_cpf(index: int) -> str:
    """Numero ficticio com estrutura CPF, sem associacao a pessoa real."""
    if not 0 <= index <= 99_999_999:
        raise ValueError("Indice fora do intervalo do identificador sintetico")
    digits = [int(char) for char in f"9{index:08d}"]
    for _ in range(2):
        remainder = sum(n * (len(digits) + 1 - i) for i, n in enumerate(digits)) * 10 % 11
        digits.append(0 if remainder == 10 else remainder)
    return "".join(map(str, digits))


def timestamp(reference: date, days_ago: int) -> str:
    return (reference - timedelta(days=days_ago)).isoformat() + "T12:00:00Z"


def cdc(payload: dict[str, str], key: str, at: str, sequence: int = 1, operation: str = "I") -> dict[str, str]:
    return {**payload, "data_atualizacao": at, "operacao": operation,
            "id_evento_cdc": f"{key}-v{sequence}", "sequencia_origem": str(sequence)}


def customer(key: str, index: int) -> dict[str, str]:
    cities = (("Sao Paulo", "SP"), ("Curitiba", "PR"), ("Recife", "PE"))
    city, state = cities[index % len(cities)]
    return {"id_cliente": key, "cpf": synthetic_cpf(index), "nome": f"Cliente Sintetico {index:06d}",
            "cidade": city, "estado": state, "renda": "5000.00", "segmento": "VAREJO"}


def account(key: str, customer_id: str, opened: str) -> dict[str, str]:
    return {"id_conta": key, "id_cliente": customer_id, "tipo_conta": "CORRENTE",
            "status_conta": "ATIVA", "data_abertura": opened[:10]}


def card(key: str, account_id: str) -> dict[str, str]:
    return {"id_cartao": key, "id_conta": account_id, "tipo_cartao": "CREDITO",
            "limite": "3000.00", "status_cartao": "ATIVO"}


def transaction(key: str, card_id: str, at: str, amount: str, **updates: str) -> dict[str, str]:
    return {"id_transacao": key, "id_cartao": card_id, "data_transacao": at,
            "valor": amount, "mcc": "5411", "estabelecimento": "Mercado Sintetico",
            "canal": "PRESENCIAL", "pais": "BR", "moeda": "BRL", "id_estabelecimento": "M001",
            "status_transacao": "APROVADA", "data_atualizacao": at, "sequencia_origem": "1", **updates}


def fixed_scenarios(reference: date) -> dict[str, dict[str, list[dict[str, str]]]]:
    batches = {batch: {source: [] for source in SOURCES} for batch in BATCH_IDS}
    initial, increment, late, evolution = (batches[batch] for batch in BATCH_IDS)
    at = lambda days: timestamp(reference, days)
    customers = [customer(f"C{i:03d}", i) for i in range(1, 4)]
    initial["clientes_cdc"] = [cdc(row, row["id_cliente"], at(180)) for row in customers]
    accounts = [account("A001", "C001", at(180)), account("A002", "C001", at(180)),
                account("A003", "C002", at(180)), account("A004", "C003", at(180))]
    initial["contas_cdc"] = [cdc(row, row["id_conta"], at(180)) for row in accounts]
    cards = [card(f"K{i:03d}", f"A{i:03d}") for i in range(1, 5)]
    initial["cartoes_cdc"] = [cdc(row, row["id_cartao"], at(180)) for row in cards]
    initial["transacoes"] = [
        transaction("T_PARTIAL", "K002", at(60), "100.00"),
        transaction("T_FULL", "K003", at(60), "80.00"),
        transaction("T_BEFORE_CANCEL", "K001", at(25), "50.00"),
        transaction("T_CANCELLED", "K002", at(40), "25.00", status_transacao="CANCELADA"),
        transaction("T_DUP", "K002", at(45), "40.00"),
        transaction("T_INVALID_AMOUNT", "K002", at(50), "abc"),
        transaction("T_FX", "K003", at(35), "15.00", moeda="USD", pais="US"),
        transaction("T_VERSION", "K002", at(50), "20.00", status_transacao="PENDENTE"),
    ]
    initial["eventos_risco"] = [{"id_evento": "E_SUSPECT", "id_transacao": "T_PARTIAL",
                                "tipo_evento": "SUSPEITA", "severidade": "MEDIA", "data_evento": at(59)}]
    initial["estornos"] = [{"id_estorno": "R_PARTIAL", "id_transacao": "T_PARTIAL", "data_estorno": at(55),
                           "motivo": "DEVOLUCAO_PARCIAL", "valor_estorno": "30.00", "moeda": "BRL"}]
    increment["clientes_cdc"] = [cdc({**customers[0], "cidade": "Campinas", "estado": "SP", "renda": "6200.00"}, "C001", at(10), 3, "U")]
    increment["contas_cdc"] = [cdc({**accounts[3], "status_conta": "ENCERRADA"}, "A004", at(5), 2, "U")]
    increment["cartoes_cdc"] = [cdc({**cards[0], "status_cartao": "CANCELADO"}, "K001", at(20), 2, "U"),
                               cdc({**cards[1], "limite": "4500.00"}, "K002", at(15), 2, "U"),
                               cdc({**cards[3], "status_cartao": "CANCELADO"}, "K004", at(5), 2, "D")]
    increment["transacoes"] = [transaction("T_AFTER_CANCEL", "K001", at(10), "60.00"),
                               transaction("T_VERSION", "K002", at(50), "20.00", data_atualizacao=at(12), sequencia_origem="2")]
    increment["eventos_risco"] = [{"id_evento": "E_CHARGEBACK", "id_transacao": "T_FULL", "tipo_evento": "CHARGEBACK", "severidade": "ALTA", "data_evento": at(8)}]
    increment["estornos"] = [{"id_estorno": "R_FULL", "id_transacao": "T_FULL", "data_estorno": at(5), "motivo": "DEVOLUCAO_TOTAL", "valor_estorno": "80.00", "moeda": "BRL"}]
    late["clientes_cdc"] = [cdc({**customers[0], "renda": "5800.00"}, "C001", at(75), 2, "U"),
                            dict(initial["clientes_cdc"][0]),
                            cdc({**customer("C_BAD", 99), "cpf": "INVALIDO"}, "C_BAD", at(3))]
    late["contas_cdc"] = [cdc(account("A_ORPHAN", "C_MISSING", at(50)), "A_ORPHAN", at(50))]
    late["cartoes_cdc"] = [cdc(card("K_ORPHAN", "A_MISSING"), "K_ORPHAN", at(50))]
    late["transacoes"] = [dict(initial["transacoes"][4]), transaction("T_LATE", "K002", at(100), "35.00"),
                           transaction("T_ORPHAN", "K_MISSING", at(70), "10.00")]
    late["eventos_risco"] = [{"id_evento": "E_ORPHAN", "id_transacao": "T_MISSING", "tipo_evento": "FRAUDE", "severidade": "ALTA", "data_evento": at(2)}]
    late["estornos"] = [{"id_estorno": "R_ORPHAN", "id_transacao": "T_MISSING", "data_estorno": at(1), "motivo": "REFERENCIA_INVALIDA", "valor_estorno": "5.00", "moeda": "BRL"}]
    evolution["transacoes"] = [transaction("T_SCHEMA", "K002", at(1), "12.50", dispositivo="mobile-sintetico")]
    return batches


SCENARIOS = {
    BATCH_IDS[0]: ["multiple_accounts_cards", "partial_refund", "cancelled_transaction", "invalid_value", "foreign_currency", "pending_transaction"],
    BATCH_IDS[1]: ["customer_update", "account_closed", "card_cancelled", "card_limit_changed", "cdc_delete", "transaction_update", "full_refund", "chargeback"],
    BATCH_IDS[2]: ["late_cdc", "duplicate_cdc", "invalid_cpf", "orphan_account", "orphan_card", "duplicate_transaction", "late_transaction", "orphan_transaction", "orphan_risk", "orphan_refund"],
    BATCH_IDS[3]: ["extra_csv_column", "empty_source_files"],
}
