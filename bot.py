import os
import shutil
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from pdf_extractor import extrair_pdf
from sheets_updater import atualizar_sheets

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados da conversa /clientes
ESCOLHER_ESTADO, ESCOLHER_CIDADE = range(2)

# Chave de estado para modo /relatorios
AGUARDANDO_PDFS = "aguardando_pdfs"

ESTADOS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
]


# ──────────────────────────────────────────────────────────────────────────────
# Comandos gerais
# ──────────────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Sou seu assistente do Demander.\n\n"
        "📋 *Comandos disponíveis:*\n"
        "/clientes — Exportar lista de clientes em Excel\n"
        "/relatorios — Enviar PDFs para atualizar o Google Sheets\n"
        "/ajuda — Ver todos os comandos",
        parse_mode="Markdown"
    )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Comandos disponíveis:*\n\n"
        "/clientes — Exportar clientes por cidade em Excel\n"
        "/relatorios — Enviar PDFs e atualizar o Google Sheets (BI)\n"
        "/processar — Processar PDFs enviados e atualizar o Sheets\n"
        "/cancelar — Cancelar operação em andamento",
        parse_mode="Markdown"
    )


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(AGUARDANDO_PDFS, None)
    context.user_data.pop("pdfs_recebidos", None)
    await update.message.reply_text("🚫 Operação cancelada.")
    return ConversationHandler.END


# ──────────────────────────────────────────────────────────────────────────────
# /clientes — fluxo existente
# ──────────────────────────────────────────────────────────────────────────────

async def clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teclado = []
    linha = []
    for i, uf in enumerate(ESTADOS):
        linha.append(InlineKeyboardButton(uf, callback_data=f"estado:{uf}"))
        if (i + 1) % 5 == 0:
            teclado.append(linha)
            linha = []
    if linha:
        teclado.append(linha)

    markup = InlineKeyboardMarkup(teclado)
    await update.message.reply_text(
        "🗺️ *Passo 1 de 2 — Selecione o estado:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    return ESCOLHER_ESTADO


async def escolher_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    estado = query.data.split(":")[1]
    context.user_data["estado"] = estado

    await query.edit_message_text(f"🔍 Buscando cidades em *{estado}*...", parse_mode="Markdown")

    try:
        scraper = DemandScraper()
        cidades = scraper.buscar_cidades(estado)
    except Exception as e:
        logger.error(f"Erro ao buscar cidades: {e}")
        await query.edit_message_text(
            "❌ Erro ao acessar o Demander. Verifique as credenciais no arquivo .env e tente novamente."
        )
        return ConversationHandler.END

    if not cidades:
        await query.edit_message_text(f"⚠️ Nenhuma cidade encontrada para *{estado}*.", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["cidades"] = cidades

    teclado = []
    for cidade in sorted(cidades):
        teclado.append([InlineKeyboardButton(cidade, callback_data=f"cidade:{cidade}")])

    markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(
        f"📍 *Passo 2 de 2 — Selecione a cidade em {estado}:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    return ESCOLHER_CIDADE


async def escolher_cidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cidade = query.data.split(":", 1)[1]
    estado = context.user_data["estado"]

    await query.edit_message_text(
        f"⏳ Exportando clientes de *{cidade} - {estado}*...\n"
        "Isso pode levar alguns segundos.",
        parse_mode="Markdown"
    )

    try:
        scraper = DemandScraper()
        caminho_excel = scraper.exportar_clientes(estado, cidade)

        with open(caminho_excel, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=f"clientes_{cidade}_{estado}.xlsx",
                caption=f"✅ Clientes de *{cidade} - {estado}* exportados com sucesso!",
                parse_mode="Markdown"
            )

        await query.edit_message_text(
            f"✅ Excel gerado para *{cidade} - {estado}*.",
            parse_mode="Markdown"
        )
        os.remove(caminho_excel)

    except Exception as e:
        logger.error(f"Erro ao exportar clientes: {e}")
        await query.edit_message_text(
            "❌ Erro ao gerar o Excel. Tente novamente ou contate o suporte."
        )

    return ConversationHandler.END


# ──────────────────────────────────────────────────────────────────────────────
# /relatorios — recebe PDFs e atualiza Google Sheets
# ──────────────────────────────────────────────────────────────────────────────

async def relatorios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ativa o modo de recebimento de PDFs."""
    context.user_data[AGUARDANDO_PDFS] = True
    context.user_data["pdfs_recebidos"] = []

    await update.message.reply_text(
        "📂 *Modo de atualização do BI ativado!*\n\n"
        "Envie os PDFs dos relatórios (um a um ou vários de uma vez).\n\n"
        "Quando terminar, envie /processar para atualizar o Google Sheets.\n"
        "Use /cancelar para sair sem processar.",
        parse_mode="Markdown"
    )


async def receber_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe cada PDF enviado durante o modo /relatorios."""
    if not context.user_data.get(AGUARDANDO_PDFS):
        return  # ignora PDFs fora do modo relatorios

    doc = update.message.document
    if doc.mime_type != "application/pdf":
        await update.message.reply_text("⚠️ Envie apenas arquivos PDF.")
        return

    # Baixa para arquivo temporário
    file = await doc.get_file()
    tmp = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False,
        prefix=doc.file_name.replace("/", "_").replace(" ", "_") + "_"
    )
    await file.download_to_drive(tmp.name)

    context.user_data["pdfs_recebidos"].append({
        "path": tmp.name,
        "name": doc.file_name
    })

    total = len(context.user_data["pdfs_recebidos"])
    await update.message.reply_text(
        f"✅ *{doc.file_name}* recebido ({total} PDF{'s' if total > 1 else ''} no total).\n"
        "Continue enviando ou use /processar quando terminar.",
        parse_mode="Markdown"
    )


async def processar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa todos os PDFs recebidos e atualiza o Google Sheets."""
    if not context.user_data.get(AGUARDANDO_PDFS):
        await update.message.reply_text("⚠️ Use /relatorios primeiro para ativar o modo de upload.")
        return

    pdfs = context.user_data.get("pdfs_recebidos", [])
    if not pdfs:
        await update.message.reply_text("⚠️ Nenhum PDF recebido ainda. Envie os arquivos primeiro.")
        return

    msg = await update.message.reply_text(
        f"⏳ Processando {len(pdfs)} PDF(s)...\nIsso pode levar alguns segundos."
    )

    todos_dados = []
    erros = []

    for item in pdfs:
        # Copia para path com nome original (o extrator usa o nome do arquivo)
        nome_arquivo = item["name"]
        novo_path = os.path.join(tempfile.gettempdir(), nome_arquivo.replace("/", "_"))
        shutil.copy2(item["path"], novo_path)
        os.remove(item["path"])

        resultado = extrair_pdf(novo_path)
        os.remove(novo_path)

        if resultado:
            todos_dados.append(resultado)
        else:
            erros.append(nome_arquivo)

    if not todos_dados:
        await msg.edit_text(
            "❌ Nenhum PDF foi reconhecido.\n"
            "Verifique se os arquivos são relatórios válidos do Demander (Vendas X Mês, Produto, etc.)."
        )
        context.user_data.pop(AGUARDANDO_PDFS, None)
        context.user_data.pop("pdfs_recebidos", None)
        return

    try:
        resumo = atualizar_sheets(todos_dados)

        if erros:
            resumo += f"\n\n⚠️ PDFs não reconhecidos ({len(erros)}):\n" + "\n".join(f"  • {e}" for e in erros)

        await msg.edit_text(resumo, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Erro ao atualizar Sheets: {e}")
        await msg.edit_text(
            f"❌ Erro ao atualizar o Google Sheets:\n`{str(e)}`\n\n"
            "Verifique GOOGLE_CREDENTIALS_JSON e SPREADSHEET_ID no Render.",
            parse_mode="Markdown"
        )

    context.user_data.pop(AGUARDANDO_PDFS, None)
    context.user_data.pop("pdfs_recebidos", None)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN não definido nas variáveis de ambiente!")

    app = Application.builder().token(token).build()

    conv_clientes = ConversationHandler(
        entry_points=[CommandHandler("clientes", clientes)],
        states={
            ESCOLHER_ESTADO: [CallbackQueryHandler(escolher_estado, pattern="^estado:")],
            ESCOLHER_CIDADE: [CallbackQueryHandler(escolher_cidade, pattern="^cidade:")],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("relatorios", relatorios))
    app.add_handler(CommandHandler("processar", processar))
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(conv_clientes)
    app.add_handler(MessageHandler(filters.Document.PDF, receber_pdf))

    logger.info("Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
