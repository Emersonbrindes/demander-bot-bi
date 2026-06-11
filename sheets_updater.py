"""
sheets_updater.py
Recebe os dados extraidos pelo pdf_extractor e atualiza as abas do Google Sheets.

Estrutura das abas:
  VENDAS X CIDADES       → linha 4+  : VENDEDOR | CIDADE | VALOR
  VENDAS X ESTADOS       → linha 4+  : VENDEDOR | ESTADO | VALOR
  VENDAS X MÊS           → linha 5+  : VENDEDOR | MÊS    | VALOR
  VENDAS X PRODUTOS      → linha 2+  : RANK | PRODUTO | VENDEDOR | VALOR
  PRODUTOS CONSOLIDADOS  → linha 2+  : RANK | PRODUTO | TOTAL | % | [col por vendedor]
  METAS X VENDAS         → linhas 14-21 (REALIZADO): valor por vendedor/mês
"""

import os
import json
import logging
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Mapeamento mês "MM/AAAA" → coluna (1-based, onde B=2 = JANEIRO)
MES_COL = {
    "01": 2,  # JANEIRO
    "02": 3,  # FEVEREIRO
    "03": 4,  # MARÇO
    "04": 5,  # ABRIL
    "05": 6,  # MAIO
    "06": 7,  # JUNHO
    "07": 8,  # JULHO
    "08": 9,  # AGOSTO
    "09": 10, # SETEMBRO
    "10": 11, # OUTUBRO
    "11": 12, # NOVEMBRO
    "12": 13, # DEZEMBRO (coluna M — TOTAL ANO está em M também; ajuste se necessário)
}

# Ordem fixa dos vendedores nas linhas do REALIZADO (linhas 14-19)
# Deve coincidir exatamente com a ordem na planilha
VENDEDORES_METAS = [
    "Adroaldo Dos Santos",
    "Cristiano Aranha",
    "Gustavo Reis",
    "Marcelo Pereira",
    "Rone Aranha",
    "Wanderson Silva",
]


def _normalizar_vendedor(nome: str) -> str:
    """Normaliza nome para comparação (title case, sem espaços extras)."""
    return nome.strip().title()


def _get_worksheet(ss: gspread.Spreadsheet, nome: str) -> gspread.Worksheet:
    """Busca aba pelo nome, tolerando variações de acento/maiúscula."""
    nome_norm = nome.strip().upper()
    for ws in ss.worksheets():
        if ws.title.strip().upper() == nome_norm:
            return ws
    raise ValueError(f"Aba não encontrada: '{nome}'. Abas disponíveis: {[w.title for w in ss.worksheets()]}")


def _conectar() -> gspread.Spreadsheet:
    """Conecta ao Google Sheets usando service account."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")

    if not creds_json or not spreadsheet_id:
        raise ValueError("GOOGLE_CREDENTIALS_JSON e SPREADSHEET_ID precisam estar no .env")

    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(spreadsheet_id)


def _remover_linhas_vendedor(ws: gspread.Worksheet, vendedor: str, primeira_linha: int):
    """Remove todas as linhas do vendedor a partir de primeira_linha (evita duplicatas)."""
    todas = ws.get_all_values()
    vendedor_norm = _normalizar_vendedor(vendedor)
    kept = [row for i, row in enumerate(todas)
            if i + 1 < primeira_linha or not row or _normalizar_vendedor(str(row[0])) != vendedor_norm]
    if len(kept) == len(todas):
        return  # nada a remover
    logger.info(f"Removendo linhas de '{vendedor}' em '{ws.title}' (reescrita em lote)")
    ws.clear()
    if kept:
        ws.update("A1", [row[:3] for row in kept])


def _atualizar_data(ws: gspread.Worksheet, periodo_fim: str):
    """Escreve 'Atualizado até: DD/MM/AAAA' na célula N1 da aba."""
    if not periodo_fim:
        return
    try:
        atual = ws.acell("N1").value or ""
        # Só atualiza se a nova data for maior que a atual
        import re as _re
        datas = _re.findall(r'\d{2}/\d{2}/\d{4}', atual)
        if datas:
            try:
                from datetime import datetime
                data_atual = datetime.strptime(datas[0], "%d/%m/%Y")
                data_nova  = datetime.strptime(periodo_fim, "%d/%m/%Y")
                if data_nova <= data_atual:
                    return
            except ValueError:
                pass  # data inválida (ex: 31/04) — atualiza mesmo assim
        ws.update("N1", [[f"Atualizado até: {periodo_fim}"]])
        logger.info(f"'{ws.title}' → Atualizado até: {periodo_fim}")
    except Exception as e:
        logger.warning(f"Não foi possível atualizar data em '{ws.title}': {e}")


def _limpar_e_escrever(ws: gspread.Worksheet, primeira_linha: int, dados: list[list]):
    """Limpa a partir de primeira_linha e escreve os dados."""
    # Descobre quantas linhas já existem para limpar
    todas = ws.get_all_values()
    ultima = len(todas)
    if ultima >= primeira_linha:
        linhas_a_limpar = ultima - primeira_linha + 1
        colunas = len(todas[0]) if todas else 10
        ws.batch_clear([f"A{primeira_linha}:{gspread.utils.rowcol_to_a1(ultima, colunas)}"])

    if dados:
        ws.update(f"A{primeira_linha}", dados)


# ──────────────────────────────────────────────────────────────────────────────
# Funções por aba
# ──────────────────────────────────────────────────────────────────────────────

def atualizar_cidades(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """Aba VENDAS X CIDADES — VENDEDOR | CIDADE | VALOR"""
    try:
        ws = _get_worksheet(ss, "VENDAS X CIDADES")
    except ValueError:
        logger.warning("Aba VENDAS X CIDADES não encontrada — ignorando")
        return
    linhas = []
    vendedores_vistos = set()
    for item in todos_dados:
        if item["tipo"] != "cidade":
            continue
        vendedores_vistos.add(item["vendedor"])
        for _, cidade, valor in item["dados"]:
            linhas.append([item["vendedor"], cidade, valor])
    if linhas:
        for v in vendedores_vistos:
            _remover_linhas_vendedor(ws, v, primeira_linha=4)
        linhas.sort(key=lambda r: -r[2])
        ws.append_rows(linhas, value_input_option="USER_ENTERED", table_range="A1")
        periodo_fim = next((i["periodo_fim"] for i in todos_dados if i["tipo"] == "cidade" and i.get("periodo_fim")), None)
        _atualizar_data(ws, periodo_fim)
        logger.info(f"VENDAS X CIDADES → {len(linhas)} linhas")


def atualizar_estados(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """Aba VENDAS X ESTADOS — VENDEDOR | ESTADO | VALOR"""
    try:
        ws = _get_worksheet(ss, "VENDAS X ESTADOS")
    except ValueError:
        logger.warning("Aba VENDAS X ESTADOS não encontrada — ignorando")
        return
    linhas = []
    vendedores_vistos = set()
    for item in todos_dados:
        if item["tipo"] != "estado":
            continue
        vendedores_vistos.add(item["vendedor"])
        for _, estado, valor in item["dados"]:
            linhas.append([item["vendedor"], estado, valor])
    if linhas:
        for v in vendedores_vistos:
            _remover_linhas_vendedor(ws, v, primeira_linha=4)
        linhas.sort(key=lambda r: -r[2])
        ws.append_rows(linhas, value_input_option="USER_ENTERED", table_range="A1")
        periodo_fim = next((i["periodo_fim"] for i in todos_dados if i["tipo"] == "estado" and i.get("periodo_fim")), None)
        _atualizar_data(ws, periodo_fim)
        logger.info(f"VENDAS X ESTADOS → {len(linhas)} linhas")


def atualizar_mes(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """Aba VENDAS X MÊS — VENDEDOR | MÊS | VALOR"""
    try:
        ws = _get_worksheet(ss, "VENDAS X MÊS")
    except ValueError:
        logger.warning("Aba VENDAS X MÊS não encontrada — ignorando")
        return
    linhas = []
    vendedores_vistos = set()
    for item in todos_dados:
        if item["tipo"] != "mes":
            continue
        vendedores_vistos.add(item["vendedor"])
        for _, mes, valor in item["dados"]:
            linhas.append([item["vendedor"], mes, valor])
    if linhas:
        for v in vendedores_vistos:
            _remover_linhas_vendedor(ws, v, primeira_linha=5)
        linhas.sort(key=lambda r: (r[0], r[1]))
        ws.append_rows(linhas, value_input_option="USER_ENTERED", table_range="A1")
        periodo_fim = next((i["periodo_fim"] for i in todos_dados if i["tipo"] == "mes" and i.get("periodo_fim")), None)
        _atualizar_data(ws, periodo_fim)
        logger.info(f"VENDAS X MÊS → {len(linhas)} linhas")


def atualizar_produtos(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """Aba VENDAS X PRODUTOS — linha 2+: VENDEDOR | PRODUTO | VALOR"""
    try:
        ws = _get_worksheet(ss, "VENDAS X PRODUTOS")
    except ValueError:
        logger.warning("Aba VENDAS X PRODUTOS não encontrada — ignorando")
        return
    linhas = []
    vendedores_vistos = set()
    for item in todos_dados:
        if item["tipo"] != "produto":
            continue
        vendedores_vistos.add(item["vendedor"])
        for _, produto, valor in item["dados"]:
            linhas.append([item["vendedor"], produto, valor])
    if linhas:
        for v in vendedores_vistos:
            _remover_linhas_vendedor(ws, v, primeira_linha=2)
        linhas.sort(key=lambda r: -r[2])
        ws.append_rows(linhas, value_input_option="USER_ENTERED", table_range="A1")
        periodo_fim = next((i["periodo_fim"] for i in todos_dados if i["tipo"] == "produto" and i.get("periodo_fim")), None)
        _atualizar_data(ws, periodo_fim)
        logger.info(f"VENDAS X PRODUTOS → {len(linhas)} linhas")


def atualizar_clientes(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """Aba VENDAS X CLIENTES — VENDEDOR | CLIENTE | VALOR"""
    try:
        ws = _get_worksheet(ss, "VENDAS X CLIENTES")
    except ValueError:
        logger.warning("Aba VENDAS X CLIENTES não encontrada — ignorando")
        return
    linhas = []
    vendedores_vistos = set()
    for item in todos_dados:
        if item["tipo"] != "cliente":
            continue
        vendedores_vistos.add(item["vendedor"])
        for _, cliente, valor in item["dados"]:
            linhas.append([item["vendedor"], cliente, valor])
    if linhas:
        for v in vendedores_vistos:
            _remover_linhas_vendedor(ws, v, primeira_linha=2)
        linhas.sort(key=lambda r: -r[2])
        ws.append_rows(linhas, value_input_option="USER_ENTERED", table_range="A1")
        periodo_fim = next((i["periodo_fim"] for i in todos_dados if i["tipo"] == "cliente" and i.get("periodo_fim")), None)
        _atualizar_data(ws, periodo_fim)
        logger.info(f"VENDAS X CLIENTES → {len(linhas)} linhas")


def atualizar_produtos_consolidados(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """
    Aba PRODUTOS CONSOLIDADOS — pivot:
    RANK | PRODUTO | TOTAL GERAL | % GERAL | [col por vendedor ordenado]
    Linha 1 = cabeçalho (não apaga), linha 2+ = dados
    """
    try:
        ws = _get_worksheet(ss, "PRODUTOS CONSOLIDADOS")
    except ValueError:
        logger.warning("Aba PRODUTOS CONSOLIDADOS não encontrada — ignorando")
        return

    # Agrega: produto → {vendedor: valor}
    produto_vendedor: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    vendedores_set = set()

    for item in todos_dados:
        if item["tipo"] != "produto":
            continue
        vendedores_set.add(item["vendedor"])
        for _, produto, valor in item["dados"]:
            produto_vendedor[produto][item["vendedor"]] += valor

    vendedores = sorted(vendedores_set)
    total_geral_global = sum(
        sum(v.values()) for v in produto_vendedor.values()
    )

    # Cabeçalho
    cabecalho = ["RANK", "PRODUTO", "TOTAL_GERAL", "PCT_GERAL"] + vendedores
    ws.update("A1", [cabecalho])

    # Linhas de dados
    totais = {p: sum(v.values()) for p, v in produto_vendedor.items()}
    produtos_ordenados = sorted(totais, key=lambda p: -totais[p])

    linhas = []
    for rank, produto in enumerate(produtos_ordenados, start=1):
        total = totais[produto]
        pct = round(total / total_geral_global * 100, 2) if total_geral_global else 0
        row = [rank, produto, total, pct]
        for v in vendedores:
            row.append(produto_vendedor[produto].get(v, 0) or "")
        linhas.append(row)

    _limpar_e_escrever(ws, 2, linhas)
    periodo_fim = next((i["periodo_fim"] for i in todos_dados if i["tipo"] == "produto" and i.get("periodo_fim")), None)
    _atualizar_data(ws, periodo_fim)
    logger.info(f"PRODUTOS CONSOLIDADOS → {len(linhas)} produtos, {len(vendedores)} vendedores")


def atualizar_realizado_metas(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """
    Aba METAS X VENDAS — seção REALIZADO 2026 (linhas 14-21).
    Estrutura: linha 14 = Adroaldo, 15 = Cristiano, ...
    Colunas B-M = Jan-Dez
    Preserva valores já existentes — só sobrescreve células com novos dados.
    """
    ws = _get_worksheet(ss, "METAS X VENDAS")

    # Agrega: vendedor → {mes_num: valor}
    novos: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for item in todos_dados:
        if item["tipo"] != "mes":
            continue
        vendedor = _normalizar_vendedor(item["vendedor"])
        for _, mes_str, valor in item["dados"]:
            mes_num = mes_str.split("/")[0] if "/" in mes_str else None
            if mes_num:
                novos[vendedor][mes_num] += valor

    if not novos:
        logger.info("METAS X VENDAS — nenhum dado de mês para atualizar")
        return

    n_vendedores = len(VENDEDORES_METAS)
    # Colunas B-L = Janeiro a Novembro (11 meses); M é ACUMULADO (fórmula, não toca)
    meses = [f"{m:02d}" for m in range(1, 12)]  # 01 a 11

    # Lê a matriz atual do Sheets para preservar valores existentes (B14:L19)
    ultima_linha = 13 + n_vendedores  # linha 19 para 6 vendedores
    atual = ws.get(f"B14:L{ultima_linha}") or []
    while len(atual) < n_vendedores:
        atual.append([])
    for i in range(n_vendedores):
        while len(atual[i]) < 11:
            atual[i].append("")

    # Mescla: só sobrescreve células com novos dados
    for row_idx, vendedor_padrao in enumerate(VENDEDORES_METAS):
        dados_v = novos.get(_normalizar_vendedor(vendedor_padrao), {})
        for col_idx, mes_num in enumerate(meses):
            if mes_num in dados_v:
                atual[row_idx][col_idx] = dados_v[mes_num]

    ws.update(f"B14:L{ultima_linha}", atual, value_input_option="USER_ENTERED")
    logger.info(f"METAS X VENDAS (REALIZADO) → B14:L{ultima_linha} atualizado, coluna M preservada")


# ──────────────────────────────────────────────────────────────────────────────
# Reparo: move dados gravados por engano nas colunas N+ de volta para A/B/C
# ──────────────────────────────────────────────────────────────────────────────

# Aba → primeira linha de dados
ABAS_REPARO = {
    "VENDAS X CIDADES": 4,
    "VENDAS X ESTADOS": 4,
    "VENDAS X MÊS": 5,
    "VENDAS X PRODUTOS": 2,
    "VENDAS X CLIENTES": 2,
}


def reparar_colunas(ss: gspread.Spreadsheet | None = None) -> str:
    """
    Corrige dados que o append_rows gravou nas colunas N/O/P (bug do table_range).
    Move o bloco para as colunas A/B/C, abaixo da última linha preenchida,
    e limpa as colunas N+ (preservando a data em N1).
    """
    if ss is None:
        ss = _conectar()

    relatorio = []
    for nome, primeira_linha in ABAS_REPARO.items():
        try:
            ws = _get_worksheet(ss, nome)
        except ValueError:
            continue

        vals = ws.get_all_values()
        bloco = []
        for i, row in enumerate(vals):
            if i == 0:
                continue  # linha 1: N1 tem 'Atualizado até' — preserva
            extra = row[13:16] if len(row) > 13 else []
            if any(str(c).strip() for c in extra):
                bloco.append((extra + ["", "", ""])[:3])

        if not bloco:
            continue

        # Última linha preenchida na coluna A
        ultima_a = 0
        for i, row in enumerate(vals):
            if row and str(row[0]).strip():
                ultima_a = i + 1
        destino = max(primeira_linha, ultima_a + 1)

        ws.update(f"A{destino}", bloco, value_input_option="USER_ENTERED")
        ws.batch_clear([f"N2:Z{len(vals)}"])
        relatorio.append(f"• {nome}: {len(bloco)} linhas movidas para A{destino}")
        logger.info(f"REPARO {nome}: {len(bloco)} linhas N→A (linha {destino})")

    return "\n".join(relatorio) if relatorio else "Nenhuma aba precisava de correção. ✅"


# ──────────────────────────────────────────────────────────────────────────────
# Função principal
# ──────────────────────────────────────────────────────────────────────────────

def atualizar_sheets(todos_dados: list[dict]) -> str:
    """
    Recebe lista de dicts do pdf_extractor e atualiza todas as abas.
    Retorna mensagem de resumo.
    """
    if not todos_dados:
        return "Nenhum dado para atualizar."

    ss = _conectar()

    contadores = {t: 0 for t in ["mes", "produto", "cidade", "estado", "cliente", "pagamento"]}
    linhas_total = {t: 0 for t in ["mes", "produto", "cidade", "estado", "cliente", "pagamento"]}
    for item in todos_dados:
        contadores[item["tipo"]] += 1
        linhas_total[item["tipo"]] += len(item["dados"])

    atualizar_cidades(ss, todos_dados)
    atualizar_estados(ss, todos_dados)
    atualizar_mes(ss, todos_dados)
    atualizar_produtos(ss, todos_dados)
    atualizar_clientes(ss, todos_dados)
    atualizar_produtos_consolidados(ss, todos_dados)
    atualizar_realizado_metas(ss, todos_dados)

    resumo = (
        f"✅ Google Sheets atualizado!\n\n"
        f"📊 PDFs processados:\n"
        f"  • Mês: {contadores['mes']} ({linhas_total['mes']} linhas)\n"
        f"  • Produto: {contadores['produto']} ({linhas_total['produto']} linhas)\n"
        f"  • Cidade: {contadores['cidade']} ({linhas_total['cidade']} linhas)\n"
        f"  • Estado: {contadores['estado']} ({linhas_total['estado']} linhas)\n"
        f"  • Cliente: {contadores['cliente']} ({linhas_total['cliente']} linhas)\n"
    )
    return resumo
