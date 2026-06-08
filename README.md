# 🤖 Bot Telegram — Só Brinde BI (@Sobrinde_bi_bot)

Bot que recebe PDFs exportados do sistema Demander, extrai os dados e atualiza automaticamente o Google Sheets com as informações de vendas por produto, cliente, cidade, estado e mês.

---

## 🔗 Links importantes

| O que | Link |
|---|---|
| **Bot no Telegram** | [@Sobrinde_bi_bot](https://t.me/Sobrinde_bi_bot) |
| **Código no GitHub** | [github.com/Emersonbrindes/demander-bot](https://github.com/Emersonbrindes/demander-bot) |
| **Servidor no Render** | [dashboard.render.com](https://dashboard.render.com/worker/srv-d8bcc0f7f7vs73bv5mhg) |
| **Logs do bot** | [Logs no Render](https://dashboard.render.com/worker/srv-d8bcc0f7f7vs73bv5mhg/logs) |
| **Google Sheets** | Planilha configurada via SPREADSHEET_ID |

---

## 📋 Como usar o bot

1. Abra o Telegram e pesquise por **@Sobrinde_bi_bot**
2. Exporte o PDF do Demander (Vendas X Produto, Vendas X Cliente, Vendas X Cidade, etc.)
3. No Telegram, toque em 📎 → **Arquivo** → selecione o PDF
4. O bot detecta o tipo de relatório automaticamente
5. Selecione o **representante** na lista exibida
6. O bot processa o PDF e atualiza o Google Sheets

**Exemplo:**
```
Você: [envia PDF "Vendas X Produto ate 31.12.24.pdf"]
Bot:  📄 Vendas X Produto recebido! Qual representante é esse relatório?
      [botões: Cristiano Aranha | Wanderson Silva | ...]
Você: [clica em Cristiano Aranha]
Bot:  ✅ Google Sheets atualizado! Produto: 1 (167 linhas)
```

**Outros comandos:**
- `/start` — apresenta o bot
- `/ajuda` — lista os comandos
- `/clientes` — exportar lista de clientes por cidade em Excel
- `/cancelar` — cancela operação em andamento

---

## 📊 Abas do Google Sheets atualizadas

| Aba | Colunas | Tipo de PDF |
|---|---|---|
| VENDAS X PRODUTOS | Vendedor \| Produto \| Valor | Vendas X Produto |
| VENDAS X CLIENTES | Vendedor \| Cliente \| Valor | Vendas X Cliente |
| VENDAS X CIDADES | Vendedor \| Cidade \| Valor | Vendas X Cidade |
| VENDAS X ESTADOS | Vendedor \| Estado \| Valor | Vendas X Estado |
| VENDAS X MÊS | Vendedor \| Mês \| Valor | Vendas X Mês |
| METAS X VENDAS | Realizado por vendedor/mês | Vendas X Mês |

**Regras de atualização:**
- Valores são **somados** quando o mesmo vendedor+produto/cliente já existe na planilha
- Planilha sempre ordenada do **maior para o menor valor**
- Produtos com diferentes variações de caixa (CX 100, CX 200...) são **unificados** em um único produto
- Códigos de produto e de cliente são **removidos** automaticamente

---

## 🏗️ Estrutura do projeto

```
demander-bot/                  ← repositório GitHub
├── requirements.txt           ← dependências Python
├── pdf_extractor.py           ← extração de dados dos PDFs (PyMuPDF)
├── sheets_updater.py          ← atualização do Google Sheets
└── demander_bot/
    ├── bot.py                 ← lógica do Telegram (bot principal)
    └── scraper.py             ← automação do Demander (exportar clientes)
```

---

## ⚙️ Configurações no Render

**Acesse:** [dashboard.render.com](https://dashboard.render.com/worker/srv-d8bcc0f7f7vs73bv5mhg)

| Campo | Valor |
|---|---|
| Tipo | Background Worker |
| Runtime | Python 3.11.9 |
| Build Command | `pip install -r requirements.txt && python -m playwright install chromium` |
| Start Command | `cd demander_bot && python bot.py` |
| Plano | Starter ($7/mês) |

**Variáveis de ambiente:**

| Variável | Descrição |
|---|---|
| `TELEGRAM_TOKEN` | Token do @Sobrinde_bi_bot (obtido no @BotFather) |
| `DEMANDER_EMAIL` | E-mail de login no Demander |
| `DEMANDER_SENHA` | Senha do Demander |
| `GOOGLE_CREDENTIALS_JSON` | JSON da conta de serviço do Google (em uma linha só) |
| `SPREADSHEET_ID` | ID da planilha Google Sheets |
| `PLAYWRIGHT_BROWSERS_PATH` | `/opt/render/project/.playwright` |

---

## 🔧 Como atualizar o código

1. Edite os arquivos em [github.com/Emersonbrindes/demander-bot](https://github.com/Emersonbrindes/demander-bot)
   - Clique no arquivo → lápis ✏️ → edita → **Commit changes**
2. O Render faz o deploy automaticamente em ~3 minutos
3. Para forçar: Render → **Manual Deploy** → **Deploy latest commit**

---

## 🐛 Problemas comuns

| Problema | Causa | Solução |
|---|---|---|
| Bot não responde ao PDF | Serviço caído ou deploy com erro | Ver logs no Render |
| "Tipo não reconhecido" | Nome do arquivo não contém palavra-chave | Renomear PDF com "produto", "cliente", "cidade", etc. |
| Erro no Google Sheets | Credenciais inválidas ou planilha errada | Verificar GOOGLE_CREDENTIALS_JSON e SPREADSHEET_ID |
| Produtos com nomes juntos | PDF de versão antiga do Demander | Verificar extração com /debug |
| Dados duplicados | PDF enviado duas vezes | O sistema soma automaticamente — não duplica |

---

## 🧰 Tecnologias utilizadas

| Tecnologia | Versão | Uso |
|---|---|---|
| Python | 3.11.9 | Linguagem principal |
| python-telegram-bot | 21.9 | Integração Telegram |
| PyMuPDF | 1.24.5 | Extração de texto dos PDFs com coordenadas |
| gspread | 6.1.2 | Atualização do Google Sheets |
| google-auth | 2.29.0 | Autenticação Google |
| Playwright | — | Automação do navegador (exportar clientes) |
| Render.com | — | Hospedagem ($7/mês) |

---

*Projeto desenvolvido com assistência do Claude (Anthropic) — Junho/2026*
