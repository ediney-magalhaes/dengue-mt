"""
keepalive.py — Mantém o dashboard Streamlit Cloud ativo
Usa Playwright (Chromium headless) para renderizar a página de fato,
contornando o problema de que curl/requests recebem apenas o shell HTML
estático sem iniciar o processo Python do app.

Referência: https://zenn.dev/shogaku/articles/streamlit-keepalive-playwright
"""

import sys
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

DASHBOARD_URL = "https://dengue-mt-ifmt.streamlit.app"
# Tempo máximo (ms) para aguardar elementos na página
TIMEOUT_MS = 120_000  # 2 minutos — apps hibernados podem demorar para iniciar


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Abrindo {DASHBOARD_URL} ...")
        page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

        # --- Cenário 1: App está dormindo → botão "Yes, get this app back up!" ---
        wake_button = page.locator("button:has-text('Yes, get this app back up')")
        try:
            wake_button.wait_for(state="visible", timeout=10_000)  # 10s para checar
            print("App estava hibernando — clicando no botão de wake-up...")
            wake_button.click()
            # Aguarda o app carregar após o wake-up
            page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
            print("Botão clicado, aguardando app iniciar...")
        except PlaywrightTimeout:
            print("Nenhum botão de wake-up encontrado — app já está ativo.")

        # --- Cenário 2: Verificar que o app realmente carregou ---
        # Streamlit renderiza o título principal como h1 ou dentro de [data-testid="stAppViewContainer"]
        try:
            page.locator('[data-testid="stAppViewContainer"]').wait_for(
                state="visible", timeout=TIMEOUT_MS
            )
            print("✅ Dashboard está ativo e renderizado com sucesso!")
            browser.close()
            sys.exit(0)
        except PlaywrightTimeout:
            print("❌ Dashboard não carregou dentro do timeout.")
            # Salva screenshot para debug (disponível nos artifacts do GitHub Actions)
            page.screenshot(path="keepalive_debug.png")
            print("Screenshot salvo em keepalive_debug.png")
            browser.close()
            sys.exit(1)


if __name__ == "__main__":
    main()