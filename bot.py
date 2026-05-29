import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler
)
from scraper import DemandScraper

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados da conversa
ESCOLHER_ESTADO, ESCOLHER_CIDADE = range(2)

# Lista de estados brasileiros
ESTADOS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — apresenta o bot."""
    await update.message.reply_text(
        "👋 Olá! Sou seu assistente do Demander.\n\n"
        "Use /clientes para exportar a lista de clientes em Excel.\n"
        "Use /ajuda para ver todos os comandos."
    )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Comandos disponíveis:*\n\n"
        "/clientes — Exportar clientes por cidade em Excel\n"
        "/start — Reiniciar o bot\n"
        "/cancelar — Cancelar operação em andamento",
        parse_mode="Markdown"
    )


async def clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o fluxo: escolha de estado."""
    # Monta teclado com estados em grade 5 colunas
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
    """Usuário escolheu um estado — busca cidades disponíveis no Demander."""
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

    # Monta teclado com as cidades encontradas
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
    """Usuário escolheu a cidade — faz scraping e gera Excel."""
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

        # Remove arquivo temporário
        os.remove(caminho_excel)

    except Exception as e:
        logger.error(f"Erro ao exportar clientes: {e}")
        await query.edit_message_text(
            "❌ Erro ao gerar o Excel. Tente novamente ou contate o suporte."
        )

    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela qualquer operação em andamento."""
    await update.message.reply_text("🚫 Operação cancelada.")
    return ConversationHandler.END


def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN não definido nas variáveis de ambiente!")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("clientes", clientes)],
        states={
            ESCOLHER_ESTADO: [CallbackQueryHandler(escolher_estado, pattern="^estado:")],
            ESCOLHER_CIDADE: [CallbackQueryHandler(escolher_cidade, pattern="^cidade:")],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(conv)

    logger.info("Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
