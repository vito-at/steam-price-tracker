from playwright.sync_api import sync_playwright

def fetch_rendered_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # иногда данные подгружаются чуть позже
        page.wait_for_timeout(1500)
        html = page.content()
        browser.close()
        return html
