import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

# Ajustar path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.scraper import deep_extract_from_website

def test_sites():
    sites = [
        "https://www.endesa.com",
        "https://www.valplus.es"
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for site in sites:
            print(f"\nProbando extracción profunda en: {site}")
            results = deep_extract_from_website(page, site)
            print(f"Resultados: {results}")
            
        browser.close()

if __name__ == "__main__":
    test_sites()
