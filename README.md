# 🤖 Bot Telegram — Exportar Clientes do Demander Web

Bot que exporta a lista de clientes do sistema [Demander Web](https://sistema.demander.com.br) em formato Excel (.xlsx), com seleção de estado e cidade direto pelo Telegram.

---

## 🔗 Links importantes

| O que | Link |
|---|---|
| **Bot no Telegram** | [@disponiveis_bot](https://t.me/disponiveis_bot) |
| **Código no GitHub** | [github.com/Emersonbrindes/demander-bot](https://github.com/Emersonbrindes/demander-bot) |
| **Servidor no Render** | [dashboard.render.com](https://dashboard.render.com/worker/srv-d8bcc0f7f7vs73bv5mhg) |
| **Logs do bot** | [dashboard.render.com/logs](https://dashboard.render.com/worker/srv-d8bcc0f7f7vs73bv5mhg/logs) |
| **Demander Web** | [sistema.demander.com.br](https://sistema.demander.com.br) |

---

## 📋 Como usar o bot

1. Abra o Telegram e pesquise por **@disponiveis_bot**
2. Envie `/clientes`
3. Digite a **sigla do estado** (ex: `PA`, `SP`, `RJ`)
4. Digite o **nome da cidade** (ex: `Brasil Novo`, `Altamira`, `Belém`)
5. Aguarde até 1 minuto — o bot envia o arquivo `.xlsx` automaticamente

**Exemplo:**
```
Você: /clientes
Bot:  🗺️ Digite a sigla do estado (ex: PA, SP, RJ):
Você: PA
Bot:  📍 Digite o nome da cidade em PA:
Você: Brasil Novo
Bot:  ⏳ Exportando clientes de Brasil Novo - PA...
Bot:  📎 [envia arquivo clientes_Brasil Novo_PA.xlsx]
```

**Outros comandos:**
- `/start` — apresenta o bot
- `/ajuda` — lista os comandos
- `/cancelar` — cancela operação em andamento

---

## ⚠️ Observações importantes

- O Demander permite **apenas uma sessão ativa por vez**. Se você estiver logado no navegador ao mesmo tempo que usa o bot, ocorrerá conflito. O bot desconecta a sessão anterior automaticamente.
- O bot usa as credenciais configuradas no Render. Não compartilhe o bot com outras pessoas sem antes criar um usuário exclusivo para ele no Demander.

---

## 🏗️ Estrutura do projeto

```
demander-bot/                  ← repositório GitHub
├── .python-version            ← Python 3.11.9
├── requirements.txt           ← dependências
└── demander_bot/
    ├── bot.py                 ← lógica do Telegram
    └── scraper.py             ← automação do Demander
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
| `TELEGRAM_TOKEN` | Token do bot (obtido no @BotFather) |
| `DEMANDER_EMAIL` | E-mail de login no Demander |
| `DEMANDER_SENHA` | Senha do Demander |
| `PLAYWRIGHT_BROWSERS_PATH` | `/opt/render/project/.playwright` |

---

## 🔧 Manutenção

### Ver se o bot está online
Acesse: [dashboard.render.com](https://dashboard.render.com/worker/srv-d8bcc0f7f7vs73bv5mhg) — deve mostrar status **"Deployed"** em verde.

### Ver logs de erro
Acesse: [dashboard.render.com/logs](https://dashboard.render.com/worker/srv-d8bcc0f7f7vs73bv5mhg/logs)

### Fazer novo deploy após atualizar código
1. Edite os arquivos em [github.com/Emersonbrindes/demander-bot](https://github.com/Emersonbrindes/demander-bot)
2. O Render faz o deploy automaticamente em ~3 minutos

### Forçar deploy manual
Acesse o Render → clique em **"Manual Deploy"** → **"Deploy latest commit"**

### Atualizar credenciais do Demander
Acesse o Render → **Environment** → **Edit** → altere `DEMANDER_EMAIL` ou `DEMANDER_SENHA`

---

## 🐛 Problemas comuns

| Problema | Causa | Solução |
|---|---|---|
| "Erro ao gerar Excel" | Erro no scraper | Ver logs no Render |
| Planilha em branco | Cidade sem clientes ou nome errado | Verificar nome da cidade no Demander |
| Bot não responde | Serviço caiu no Render | Fazer Manual Deploy |
| "Cidade não encontrada" | Nome digitado diferente do cadastro | Usar nome exato como aparece no Demander |
| Conflito de sessão | Logado no navegador ao mesmo tempo | O bot desconecta automaticamente |

---

## 🧰 Tecnologias usadas

| Tecnologia | Versão | Uso |
|---|---|---|
| Python | 3.11.9 | Linguagem principal |
| python-telegram-bot | 21.5 | Integração Telegram |
| Playwright | 1.44.0 | Automação do navegador |
| requests | 2.31.0 | Chamadas à API do Demander |
| openpyxl | 3.1.2 | Geração do Excel |
| Render.com | — | Hospedagem ($7/mês) |

---

*Projeto desenvolvido com assistência do Claude (Anthropic) — Junho/2026*
