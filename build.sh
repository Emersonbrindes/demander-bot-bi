#!/usr/bin/env bash
# Instala dependências Python
pip install -r requirements.txt

# Instala o browser Chromium usado pelo Playwright
playwright install chromium
playwright install-deps chromium
