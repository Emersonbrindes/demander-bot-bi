"""
sheets_updater.py
Recebe os dados extraídos pelo pdf_extractor e atualiza as abas do Google Sheets.

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

# Ordem fixa dos vendedores nas linhas do REALIZADO (linhas 14-21 = índices 0-7)
VENDEDORES_METAS = [
    "Adroaldo Dos Santos",
    "Cristiano Aranha",
    "Emerson Barbosa",
    "Gustavo Reis",
    "Marcelo Pereira",
    "Rone Aranha",
    "Wanderson Silva",
    "Wellington Rodrigues",
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
    """Aba VENDAS X CIDADES — linha 4+: VENDEDOR | CIDADE | VALOR"""
    ws = _get_worksheet(ss,"VENDAS X CIDADES")
    linhas = []
    for item in todos_dados:
        if item["tipo"] != "cidade":
            continue
        for _, cidade, valor in item["dados"]:
            linhas.append([item["vendedor"], cidade, valor])
    linhas.sort(key=lambda r: (r[0], -r[2]))
    _limpar_e_escrever(ws, 4, linhas)
    logger.info(f"VENDAS X CIDADES → {len(linhas)} linhas")


def atualizar_estados(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """Aba VENDAS X ESTADOS — linha 4+: VENDEDOR | ESTADO | VALOR"""
    ws = _get_worksheet(ss,"VENDAS X ESTADOS")
    linhas = []
    for item in todos_dados:
        if item["tipo"] != "estado":
            continue
        for _, estado, valor in item["dados"]:
            linhas.append([item["vendedor"], estado, valor])
    linhas.sort(key=lambda r: (r[0], -r[2]))
    _limpar_e_escrever(ws, 4, linhas)
    logger.info(f"VENDAS X ESTADOS → {len(linhas)} linhas")


def atualizar_mes(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """Aba VENDAS X MÊS — linha 5+: VENDEDOR | MÊS | VALOR"""
    ws = _get_worksheet(ss,"VENDAS X MÊS")
    linhas = []
    for item in todos_dados:
        if item["tipo"] != "mes":
            continue
        for _, mes, valor in item["dados"]:
            linhas.append([item["vendedor"], mes, valor])
    linhas.sort(key=lambda r: (r[0], r[1]))
    _limpar_e_escrever(ws, 5, linhas)
    logger.info(f"VENDAS X MÊS → {len(linhas)} linhas")


def atualizar_produtos(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """Aba VENDAS X PRODUTOS — linha 2+: RANK | PRODUTO | VENDEDOR | VALOR"""
    ws = _get_worksheet(ss,"VENDAS X PRODUTOS")
    linhas = []
    for item in todos_dados:
        if item["tipo"] != "produto":
            continue
        for rank, produto, valor in item["dados"]:
            linhas.append([rank, produto, item["vendedor"], valor])
    linhas.sort(key=lambda r: (r[2], r[0]))  # por vendedor, depois rank
    _limpar_e_escrever(ws, 2, linhas)
    logger.info(f"VENDAS X PRODUTOS → {len(linhas)} linhas")


def atualizar_produtos_consolidados(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """
    Aba PRODUTOS CONSOLIDADOS — pivot:
    RANK | PRODUTO | TOTAL GERAL | % GERAL | [col por vendedor ordenado]
    Linha 1 = cabeçalho (não apaga), linha 2+ = dados
    """
    ws = _get_worksheet(ss,"PRODUTOS CONSOLIDADOS")

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
    logger.info(f"PRODUTOS CONSOLIDADOS → {len(linhas)} produtos, {len(vendedores)} vendedores")


def atualizar_realizado_metas(ss: gspread.Spreadsheet, todos_dados: list[dict]):
    """
    Aba METAS X VENDAS — seção REALIZADO 2026 (linhas 14-21).
    Estrutura: linha 14 = Adroaldo, 15 = Cristiano, ...
    Colunas B-M = Jan-Dez
    Limpa apenas as células de valor (B14:M21) e reescreve.
    """
    ws = _get_worksheet(ss,"METAS X VENDAS")

    # Agrega: vendedor → {mes_num: valor}
    realizado: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for item in todos_dados:
        if item["tipo"] != "mes":
            continue
        vendedor = _normalizar_vendedor(item["vendedor"])
        for _, mes_str, valor in item["dados"]:
            # mes_str formato "MM/AAAA"
            mes_num = mes_str.split("/")[0] if "/" in mes_str else None
            if mes_num:
                realizado[vendedor][mes_num] += valor

    # Monta matriz 8 linhas × 12 colunas (Jan-Dez)
    matriz = []
    for vendedor_padrao in VENDEDORES_METAS:
        linha = []
        dados_v = realizado.get(_normalizar_vendedor(vendedor_padrao), {})
        for mes_num in [f"{m:02d}" for m in range(1, 13)]:
            linha.append(dados_v.get(mes_num, ""))
        matriz.append(linha)

    # Escreve em B14:M21
    ws.update("B14:M21", matriz)
    logger.info("METAS X VENDAS (REALIZADO) → atualizado")


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
