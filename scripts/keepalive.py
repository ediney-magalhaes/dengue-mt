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
TIMEOUT_MS = 180_000  # 3 minutos — apps hibernados podem demorar


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print(f"Abrindo {DASHBOARD_URL} ...")
            # domcontentloaded em vez de networkidle — Streamlit usa WebSocket
            # que nunca fica "idle", causando timeout
            page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=60_000)
            print("Página HTML carregada, aguardando app renderizar...")

            # --- Cenário 1: App está dormindo → botão de wake-up ---
            wake_button = page.locator("button:has-text('Yes, get this app back up')")
            try:
                wake_button.wait_for(state="visible", timeout=30_000)
                print("App estava hibernando — clicando no botão de wake-up...")
                wake_button.click()
                print("Botão clicado, aguardando app iniciar...")
                # Após clicar, espera o app carregar
                page.wait_for_timeout(10_000)  # 10s para o Streamlit iniciar
            except PlaywrightTimeout:
                print("Nenhum botão de wake-up — app já está ativo ou carregando.")

            # --- Cenário 2: Verificar que o app carregou ---
            try:
                page.locator("text=Sistema Preditivo de Dengue").wait_for(
                    state="visible", timeout=TIMEOUT_MS
                )
                print("✅ Dashboard está ativo e renderizado com sucesso!")
                browser.close()
                sys.exit(0)
            except PlaywrightTimeout:
                content_length = len(page.content())
                if content_length > 10_000:
                    print(f"✅ Dashboard ativo (conteúdo: {content_length:,} bytes)")
                    browser.close()
                    sys.exit(0)
                else:
                    print(f"❌ Dashboard não carregou (conteúdo: {content_length:,} bytes)")
                    page.screenshot(path="keepalive_debug.png")
                    print("Screenshot salvo em keepalive_debug.png")
                    browser.close()
                    sys.exit(1)

        except PlaywrightTimeout:
            print("❌ Timeout no carregamento inicial da página.")
            page.screenshot(path="keepalive_debug.png")
            print("Screenshot salvo em keepalive_debug.png")
            browser.close()
            sys.exit(1)
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            try:
                page.screenshot(path="keepalive_debug.png")
                print("Screenshot salvo em keepalive_debug.png")
            except Exception:
                pass
            browser.close()
            sys.exit(1)


if __name__ == "__main__":
    main()