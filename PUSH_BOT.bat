@echo off
echo ============================================
echo  ATUALIZANDO BOT NO GITHUB
echo ============================================

cd /d "C:\Users\Usuario\Desktop\Projeto demander_bot"

echo Removendo lock do git (se existir)...
del /F /Q ".git\index.lock" 2>nul
echo OK

echo Abortando rebase (se existir)...
git rebase --abort 2>nul

echo Adicionando arquivo...
git add demander_bot\bot.py

echo Fazendo commit...
git commit -m "fix: demander_bot/bot.py com sys.path e fluxo PDF direto"

echo Enviando para GitHub...
git push origin main --force

echo.
echo ============================================
echo  PRONTO! Verifique o Render em alguns minutos.
echo  Se apareceu "Everything up-to-date", o codigo
echo  ja estava correto. O Render vai usar a versao
echo  atual.
echo ============================================
echo.
pause
