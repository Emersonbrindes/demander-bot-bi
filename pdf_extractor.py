"""
pdf_extractor.py
Extrai dados dos relatórios PDF do Demander (Vendas X Mês, Produto, Cliente, etc.)
e retorna listas de dicts prontas para o sheets_updater.
"""

import re
import logging
import pdfplumber
from pathlib import Path

logger = logging.getLogger(__name__)

# Mapeamento mês numérico → nome em português (para aba METAS X VENDAS)
MES_NOME = {
    "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARÇO",
    "04": "ABRIL",   "05": "MAIO",      "06": "JUNHO",
    "07": "JULHO",   "08": "AGOSTO",    "09": "SETEMBRO",
    "10": "OUTUBRO", "11": "NOVEMBRO",  "12": "DEZEMBRO",
}


def detectar_tipo(filename: str) -> str | None:
    """Detecta o tipo de relatório pelo nome do arquivo."""
    fn = filename.lower()
    if "mês" in fn or "mes" in fn:
        return "mes"
    if "produto" in fn:
        return "produto"
    if "cliente" in fn:
        return "cliente"
    if "cidade" in fn:
        return "cidade"
    if "estado" in fn:
        return "estado"
    if "condição" in fn or "condicao" in fn or "pagamento" in fn:
        return "pagamento"
    return None


def extrair_vendedor(pdf_path: str) -> str:
    """Extrai o nome do vendedor do cabeçalho do PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text() or ""
            # Padrão: "N - NOME SOBRENOME"
            match = re.search(r'\d+\s*-\s*([A-ZÁÉÍÓÚÃÕÇÂÊÔ][A-ZÁÉÍÓÚÃÕÇÂÊÔA-Z\s]+)', text)
            if match:
                return match.group(1).strip().title()
    except Exception as e:
        logger.warning(f"Não conseguiu extrair vendedor de {pdf_path}: {e}")
    return Path(pdf_path).parent.name  # fallback: nome da pasta


def limpar_valor(texto: str) -> float | None:
    """Converte 'R$ 1.234,56' → 1234.56"""
    if not texto:
        return None
    limpo = re.sub(r'[R$\s]', '', str(texto)).replace('.', '').replace(',', '.')
    try:
        return float(limpo)
    except ValueError:
        return None


def extrair_tabela_pdf(pdf_path: str) -> list[list]:
    """
    Lê todas as páginas do PDF e retorna as linhas de dados
    como lista de listas [rank, col_categoria, valor_float].
    Tenta primeiro via tabela, depois via texto linha a linha.
    """
    rows = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Tentativa 1: extração por tabela
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 3:
                            continue
                        rank_str = str(row[0] or "").strip()
                        if not rank_str.isdigit():
                            continue

                        valor_raw = str(row[-2] or "")
                        valor = limpar_valor(valor_raw)
                        if valor is None:
                            continue

                        categoria = " ".join(
                            str(c or "").strip()
                            for c in row[1:-2]
                            if str(c or "").strip()
                        )
                        rows.append([int(rank_str), categoria, valor])

                # Tentativa 2: fallback por texto (pdfplumber não encontrou tabela)
                if not rows:
                    texto = page.extract_text() or ""
                    logger.info(f"TEXTO BRUTO: {repr(texto[:600])}")
                    for linha in texto.split("\n"):
                        linha = linha.strip()
                        # Padrão: linha contém R$ — split nele
                        if "R$" not in linha:
                            continue
                        partes = linha.split("R$", 1)
                        antes = partes[0].strip().split()
                        depois = partes[1].strip()
                        # antes deve começar com número (rank)
                        if not antes or not antes[0].isdigit():
                            continue
                        rank = int(antes[0])
                        categoria = " ".join(antes[1:]).strip()
                        if not categoria:
                            continue
                        # valor é o primeiro token numérico após R$
                        valor_match = re.match(r'([\d.,]+)', depois)
                        if not valor_match:
                            continue
                        valor = limpar_valor("R$" + valor_match.group(1))
                        if valor is not None:
                            rows.append([rank, categoria, valor])

    except Exception as e:
        logger.error(f"Erro ao ler PDF {pdf_path}: {e}")

    logger.info(f"  Linhas extraídas: {len(rows)}")
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Funções públicas — retornam dicts prontos para o sheets_updater
# ──────────────────────────────────────────────────────────────────────────────

def extrair_pdf(pdf_path: str) -> dict:
    """
    Processa um PDF e retorna:
    {
        "tipo": "mes" | "produto" | "cidade" | "estado" | "cliente" | "pagamento",
        "vendedor": "Nome Vendedor",
        "dados": [[rank, categoria, valor], ...]
    }
    Retorna None se o tipo não for reconhecido.
    """
    tipo = detectar_tipo(Path(pdf_path).name)
    if tipo is None:
        logger.warning(f"Tipo não reconhecido: {pdf_path}")
        return None

    vendedor = extrair_vendedor(pdf_path)
    dados = extrair_tabela_pdf(pdf_path)

    logger.info(f"  {Path(pdf_path).name} → {vendedor} | {tipo} | {len(dados)} linhas")
    return {"tipo": tipo, "vendedor": vendedor, "dados": dados}
