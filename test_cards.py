import requests
from bs4 import BeautifulSoup

base_url = "http://127.0.0.1:5000"
r = requests.get(f"{base_url}/")
soup = BeautifulSoup(r.text, 'html.parser')

print("ALL SERVICE CARDS ON HOMEPAGE:")
print("-" * 70)
service_cards = soup.find_all('article', class_='service-card')
print(f"Found {len(service_cards)} service cards\n")
for i, card in enumerate(service_cards, 1):
    title = card.find('h3')
    desc = card.find('p')
    if title:
        print(f"{i}. {title.text}")
        if desc:
            print(f"   {desc.text[:60]}...")
        print()

print("\nALL PROJECT CARDS ON HOMEPAGE:")
print("-" * 70)
project_cards = soup.find_all('article', class_='project-card')
print(f"Found {len(project_cards)} project cards\n")
for i, card in enumerate(project_cards, 1):
    title = card.find('h3')
    if title:
        print(f"{i}. {title.text}")
