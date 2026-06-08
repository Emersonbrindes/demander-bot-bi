import sys
import os

# Adiciona a pasta raiz ao path para importar pdf_extractor, sheets_updater, scraper
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from pdf_extractor import extrair_pdf, detectar_tipo
from sheets_updater import atualizar_sheets

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ESCOLHER_ESTADO, ESCOLHER_CIDADE = range(2)

ESTADOS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
]

VENDEDORES = [
    "Adroaldo Dos Santos",
    "Cristiano Aranha",
    "Gustavo Reis",
    "Marcelo Pereira",
    "Rone Aranha",
    "Wanderson Silva",
]

TIPO_LABEL = {
    "mes":       "Vendas X Mês",
    "produto":   "Vendas X Produto",
    "cidade":    "Vendas X Cidade",
    "estado":    "Vendas X Estado",
    "cliente":   "Vendas X Cliente",
    "pagamento": "Vendas X Pagamento",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Sou seu assistente do Demander.\n\n"
        "📋 *Como usar:*\n"
        "• Envie um PDF do Demander → eu pergunto o representante → atualizo o Google Sheets\n"
        "• /clientes — Exportar lista de clientes em Excel\n"
        "• /ajuda — Ver todos os comandos",
        parse_mode="Markdown"
    )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Como usar o bot:*\n\n"
        "1️⃣ Exporte o PDF do Demander\n"
        "2️⃣ Envie o PDF aqui pelo ícone 📎 → *Arquivo*\n"
        "3️⃣ Selecione o representante\n"
        "4️⃣ O Sheets é atualizado automaticamente!\n\n"
        "/clientes — Exportar clientes por cidade em Excel\n"
        "/cancelar — Cancelar operação em andamento",
        parse_mode="Markdown"
    )


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pdf_pendente", None)
    await update.message.reply_text("🚫 Operação cancelada.")
    return ConversationHandler.END


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
        from scraper import DemandScraper
        scraper = DemandScraper()
        cidades = scraper.buscar_cidades(estado)
    except Exception as e:
        logger.error(f"Erro ao buscar cidades: {e}")
        await query.edit_message_text("❌ Erro ao acessar o Demander. Verifique as credenciais e tente novamente.")
        return ConversationHandler.END
    if not cidades:
        await query.edit_message_text(f"⚠️ Nenhuma cidade encontrada para *{estado}*.", parse_mode="Markdown")
        return ConversationHandler.END
    context.user_data["cidades"] = cidades
    teclado = [[InlineKeyboardButton(c, callback_data=f"cidade:{c}")] for c in sorted(cidades)]
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
    await query.edit_message_text(f"⏳ Exportando clientes de *{cidade} - {estado}*...", parse_mode="Markdown")
    try:
        from scraper import DemandScraper
        scraper = DemandScraper()
        caminho_excel = scraper.exportar_clientes(estado, cidade)
        with open(caminho_excel, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=f"clientes_{cidade}_{estado}.xlsx",
                caption=f"✅ Clientes de *{cidade} - {estado}* exportados!",
                parse_mode="Markdown"
            )
        await query.edit_message_text(f"✅ Excel gerado para *{cidade} - {estado}*.", parse_mode="Markdown")
        os.remove(caminho_excel)
    except Exception as e:
        logger.error(f"Erro ao exportar clientes: {e}")
        await query.edit_message_text("❌ Erro ao gerar o Excel. Tente novamente.")
    return ConversationHandler.END


async def receber_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text(
            "⚠️ Envie o arquivo PDF pelo ícone 📎 → *Arquivo* (não pela câmera).",
            parse_mode="Markdown"
        )
        return
    doc = update.message.document
    if doc.mime_type != "application/pdf":
        await update.message.reply_text("⚠️ Envie apenas arquivos PDF.")
        return
    try:
        file = await doc.get_file()
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        await file.download_to_drive(tmp.name)
        tmp.close()
        tipo = detectar_tipo(doc.file_name, tmp.name)
        if tipo is None:
            os.remove(tmp.name)
            await update.message.reply_text(
                "❌ Não reconheci esse tipo de relatório.\n\n"
                "Envie PDFs do Demander: *Vendas X Mês*, *Produto*, *Cidade*, *Estado* ou *Cliente*.",
                parse_mode="Markdown"
            )
            return
        context.user_data["pdf_pendente"] = {"path": tmp.name, "name": doc.file_name, "tipo": tipo}
        teclado = []
        for i in range(0, len(VENDEDORES), 2):
            linha = [InlineKeyboardButton(VENDEDORES[i], callback_data=f"rep:{VENDEDORES[i]}")]
            if i + 1 < len(VENDEDORES):
                linha.append(InlineKeyboardButton(VENDEDORES[i + 1], callback_data=f"rep:{VENDEDORES[i + 1]}"))
            teclado.append(linha)
        markup = InlineKeyboardMarkup(teclado)
        await update.message.reply_text(
            f"📄 *{TIPO_LABEL.get(tipo, tipo)}* recebido!\n\n👤 Qual representante é esse relatório?",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Erro ao receber PDF {doc.file_name}: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Erro ao processar o arquivo:\n`{e}`",
            parse_mode="Markdown"
        )


async def escolher_representante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vendedor = query.data.split(":", 1)[1]
    pdf = context.user_data.pop("pdf_pendente", None)
    if not pdf:
        await query.edit_message_text("❌ PDF não encontrado. Envie o arquivo novamente.")
        return
    msg = await query.edit_message_text(
        f"⏳ Processando *{TIPO_LABEL.get(pdf['tipo'], pdf['tipo'])}* de *{vendedor}*...",
        parse_mode="Markdown"
    )
    resultado = extrair_pdf(pdf["path"])
    os.remove(pdf["path"])
    if not resultado or not resultado.get("dados"):
        await msg.edit_text("❌ Não foi possível extrair dados do PDF.")
        return
    resultado["vendedor"] = vendedor
    try:
        resumo = atualizar_sheets([resultado])
        await msg.edit_text(resumo)
    except Exception as e:
        logger.error(f"Erro ao atualizar Sheets: {e}")
        await msg.edit_text(
            f"❌ Erro ao atualizar o Google Sheets:\n{str(e)}\n\n"
            "Verifique GOOGLE_CREDENTIALS_JSON e SPREADSHEET_ID no Render."
        )


async def receber_foto_invalida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Você enviou uma *foto*, não um PDF.\nUse 📎 → *Arquivo* para enviar PDFs.",
        parse_mode="Markdown"
    )


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
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(conv_clientes)
    app.add_handler(CallbackQueryHandler(escolher_representante, pattern="^rep:"))
    app.add_handler(MessageHandler(filters.Document.PDF, receber_pdf))
    app.add_handler(MessageHandler(filters.PHOTO, receber_foto_invalida))
    logger.info("Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
