
import requests
from bs4 import BeautifulSoup

def scrape_bsr_table_by_country(domain_id: int):
    """
    Scrapes the BSR table from SellerAmp for a specific country domain.
    """
    url = f"https://sas.selleramp.com/sas/bsr-tables?domain_id={domain_id}&src="
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching BSR table for domain {domain_id}: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')
    if not table:
        print(f"BSR table not found for domain {domain_id}.")
        return None

    headers = [th.text.strip() for th in table.find_all('th')]
    bsr_data = {}

    for row in table.find('tbody').find_all('tr'):
        cells = row.find_all('td')
        if not cells:
            continue

        category = cells[0].text.strip()
        # Skip the 'Product Count' column (index 1)
        values = [cell.text.strip().replace(',', '') for cell in cells[2:]]
        
        category_data = {}
        # Start from the 3rd header ('Top 0.5% BSR')
        for i, header in enumerate(headers[2:]):
             if i < len(values) and values[i].isdigit():
                category_data[header] = int(values[i])

        bsr_data[category] = category_data

    return bsr_data
