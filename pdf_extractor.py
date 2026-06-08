import re
import logging
import fitz
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

ROW_TOL = 3
PRODUCT_CODE_RE = re.compile(r'^\d{8,}$')
CLIENT_CODE_RE  = re.compile(r'^\d+\s*-\s*\d+\s*-\s*')
CX_RE           = re.compile(r'\s+CX\s+\d+.*$', re.IGNORECASE)


def _palavras_por_linha(page):
    words = page.get_text('words')
    rows = {}
    for w in words:
        x0, y0, txt = w[0], w[1], w[4]
        y_key = round(y0 / ROW_TOL) * ROW_TOL
        rows.setdefault(y_key, []).append((x0, txt))
    return [(y, sorted(rows[y])) for y in sorted(rows)]


def _is_noise(texts):
    line = ' '.join(texts)
    if re.search(r'p[áa]gina\s+\d+', line, re.I): return True
    if re.search(r'www\.|emitido|demander\.com', line, re.I): return True
    if re.search(r'^\d+\.\d+\.\d+', line): return True
    return False


def _limpar_valor(txt):
    limpo = re.sub(r'[R$\s]', '', txt).replace('.', '').replace(',', '.')
    try:
        return float(limpo)
    except ValueError:
        return None


def detectar_tipo(filename, pdf_path=None):
    fn = filename.lower()
    if 'mes' in fn or 'mês' in fn: return 'mes'
    if 'produto' in fn: return 'produto'
    if 'cliente' in fn: return 'cliente'
    if 'cidade' in fn: return 'cidade'
    if 'estado' in fn: return 'estado'
    if 'pagamento' in fn or 'condicao' in fn or 'condição' in fn: return 'pagamento'
    if pdf_path:
        try:
            doc = fitz.open(pdf_path)
            text = doc[0].get_text().lower()
            for kw, tp in [('vendas x mês','mes'),('vendas x mes','mes'),
                           ('vendas x produto','produto'),('vendas x cliente','cliente'),
                           ('vendas x cidade','cidade'),('vendas x estado','estado'),
                           ('pagamento','pagamento')]:
                if kw in text: return tp
        except: pass
    return None


def extrair_vendedor(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = doc[0].get_text()
        m = re.search(r'\d+\s*-\s*([A-ZÁÉÍÓÚÃÕÇÂÊÔ][A-ZÁÉÍÓÚÃÕÇÂÊÔA-Z\s]+)', text)
        if m: return m.group(1).strip().title()
    except: pass
    return Path(pdf_path).stem


def _extrair_produto(pdf_path):
    doc = fitz.open(pdf_path)
    all_rows = []
    for page in doc:
        for _, items in _palavras_por_linha(page):
            texts = [t for _, t in items]
            if not _is_noise(texts):
                all_rows.append(texts)

    groups = []
    current = None
    for texts in all_rows:
        has_code = any(PRODUCT_CODE_RE.match(t) for t in texts)
        if has_code:
            current = {'texts': list(texts)}
            groups.append(current)
        elif current:
            current['texts'].extend(texts)

    unified = defaultdict(float)
    rank_map = {}

    for g in groups:
        texts = g['texts']
        rank = None
        valor = None
        produto_parts = []
        i = 0
        while i < len(texts):
            t = texts[i]
            if re.match(r'^\d{1,4}$', t) and rank is None and not PRODUCT_CODE_RE.match(t):
                rank = int(t)
            elif t == 'R$' and i + 1 < len(texts):
                v = _limpar_valor(texts[i + 1])
                if v: valor = v
                i += 1
            elif re.search(r'[\d,]+%', t):
                pass
            elif PRODUCT_CODE_RE.match(t) or t in ('-', 'R$', '%'):
                pass
            else:
                produto_parts.append(t)
            i += 1

        produto = ' '.join(produto_parts)
        produto = CX_RE.sub('', produto).strip()
        produto = re.sub(r'[\s\-]+$', '', produto).strip()

        if valor and produto:
            if produto not in rank_map and rank:
                rank_map[produto] = rank
            unified[produto] += valor

    return [
        [rank_map.get(p, 0), p, v]
        for p, v in sorted(unified.items(), key=lambda x: -x[1])
    ]


def _extrair_simples(pdf_path):
    doc = fitz.open(pdf_path)
    results = []
    for page in doc:
        for _, items in _palavras_por_linha(page):
            texts = [t for _, t in items]
            if _is_noise(texts): continue
            if len(texts) < 3: continue
            if not re.match(r'^\d{1,4}$', texts[0]): continue
            rank = int(texts[0])
            valor = None
            nome_parts = []
            i = 1
            while i < len(texts):
                t = texts[i]
                if t == 'R$' and i + 1 < len(texts):
                    valor = _limpar_valor(texts[i + 1])
                    break
                nome_parts.append(t)
                i += 1
            nome_raw = ' '.join(nome_parts)
            nome = CLIENT_CODE_RE.sub('', nome_raw).strip()
            nome = re.sub(r'[\#\*\&]+$', '', nome).strip()
            if valor and nome:
                results.append([rank, nome, valor])
    return results


def extrair_tabela_pdf(pdf_path, tipo=None):
    if tipo == 'produto':
        return _extrair_produto(pdf_path)
    return _extrair_simples(pdf_path)


def extrair_pdf(pdf_path):
    tipo = detectar_tipo(Path(pdf_path).name, pdf_path)
    if tipo is None:
        logger.warning(f'Tipo não reconhecido: {pdf_path}')
        return None
    vendedor = extrair_vendedor(pdf_path)
    dados = extrair_tabela_pdf(pdf_path, tipo)
    logger.info(f'{Path(pdf_path).name} -> {vendedor} | {tipo} | {len(dados)} linhas')
    return {'tipo': tipo, 'vendedor': vendedor, 'dados': dados}
