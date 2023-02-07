import chromedriver_autoinstaller
import chromedriver_binary
import pandas as pd
import re
import requests
import time

from bs4 import BeautifulSoup
from pprint import pprint
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


chromedriver_autoinstaller.install()  # Check if the current version of chromedriver exists
                                      # and if it doesn't exist, download it automatically,
                                      # then add chromedriver to path

google_sheet_html_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTw9heZuO7Oofx0utlL3oF1XGhbY8Zv9DQNO-Gkgr5NenNMywk0GwcjX72RlgLh9SRuKapoHQ2o5WLj/pubhtml?gid=0&amp;single=true'
scryfall = 'https://api.scryfall.com'

# Get HTML of Google sheet
req = requests.get(google_sheet_html_url)
soup = BeautifulSoup(req.text, 'html.parser')

# Setup Chrome webdriver options
delay = 5
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--single-process')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--log-level=3')

# Loop through HTML table rows and pull deck name and list URL
base_decklists = []
for link in soup.findAll('a'):
    if 'moxfield' in link['href']:
        base_decklists.append({
            'name': link.text,
            'url': link['href'].replace('https://www.google.com/url?q=', '').split('&', 1)[0]  # Probably not the cleanest way of doing this, but this gets the Moxfield URL without any additional wrappers
        })
pprint(base_decklists)

# Loop through decks and pull card data from URL
cards = {}
decklists = []
for deck in base_decklists:
    deck_name = deck['name']
    deck_url = deck['url']
    
    print(f'Checking {deck_name}')
    
    driver = webdriver.Chrome(options=options)
    driver.get(deck_url)
    try:
        last_updated = WebDriverWait(driver, delay).until(EC.presence_of_element_located((By.ID, 'lastupdated'))).text
        
        decklists.append({
            'name': deck_name,
            'url': deck_url,
            'last_updated': last_updated
        })
        
        # Get card names and increment card count
        deckview_element = driver.find_element(By.CLASS_NAME, 'deckview')
        for deck_row in deckview_element.find_elements(By.CLASS_NAME, 'deck-group-row'):
            card_count = re.search('(\d+)', deck_row.text).group(0)
            card_name = deck_row.find_element(By.CLASS_NAME, 'w-100').text
            if card_name not in cards:
                cards[card_name] = {}
                cards[card_name]['total'] = 1
            else:
                cards[card_name]['total'] += 1
    except Exception as err:
        print(f'{err} with deck: {deck_name} - {deck_url}')
    
    driver.close()

# Save file for last update times
decklist_df = pd.DataFrame()
for deck in decklists:
    decklist_df = decklist_df.append({'deck': deck['name'], 'last_updated': deck['last_updated'], 'url': deck['url']}, ignore_index=True)
decklist_df.to_excel('.\decklist_updates.xlsx', index=False)

# Get additional card data from Scryfall
print(f'{len(cards)} total unique cards')
for card in cards:
    card_url_name = card.replace(' ', '+')
    print(f'Retrieving Scryfall data for: {card_url_name}')
    r = requests.get(scryfall + f'/cards/named?exact={card_url_name}')
    card_data = r.json()
    cards[card]['cmc'] = card_data['cmc']
    cards[card]['color_identity'] = card_data['color_identity']
    cards[card]['type'] = card_data['type_line']
    time.sleep(0.5)

# Create and save dataframe for card details
card_df = pd.DataFrame()
for card in cards:
    card_df = card_df.append({
        'card': card,
        'count': cards[card]['total'],
        'cmc': cards[card]['cmc'],
        'color_identity': cards[card]['color_identity'],
        'type': cards[card]['type']
    }, ignore_index=True)
card_df.to_excel('.\card_count.xlsx', index=False)

print('Complete')
