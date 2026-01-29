import requests
import time
import math

def fetch_all_bills(ga_id=153, page_size=100):
    """Fetch all bills from GA 153 across multiple pages"""
    
    url = "https://legis.delaware.gov/json/AllLegislation/GetAllLegislation"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Referer": "https://legis.delaware.gov/AllLegislation",
        "Accept": "*/*"
    }
    
    bills = []
    page = 1
    
    # Get first page to determine total
    print(f"Fetching page 1...")
    data = {
        "sort": "",
        "page": page,
        "pageSize": page_size,
        "group": "",
        "filter": "",
        "selectedGA[0]": ga_id,
        "sponsorName": "",
        "fromIntroDate": "",
        "toIntroDate": "",
        "coSponsorCheck": False
    }
    
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    result = response.json()
    
    total = result['Total']
    bills.extend(result['Data'])
    print(f"Total bills: {total}")
    print(f"Got {len(result['Data'])} bills from page 1")
    
    # Calculate remaining pages
    total_pages = math.ceil(total / page_size)
    print(f"Total pages to fetch: {total_pages}")
    
    # Fetch remaining pages
    for page in range(2, total_pages + 1):
        print(f"Fetching page {page}/{total_pages}...")
        data["page"] = page
        
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        result = response.json()
        
        bills.extend(result['Data'])
        print(f"Got {len(result['Data'])} bills from page {page}")
        
        time.sleep(0.2)  # Rate limiting - be nice to their server
    
    print(f"\nTotal bills fetched: {len(bills)}")
    return bills


# Test it
if __name__ == "__main__":
    bills = fetch_all_bills()
    
    # Show some sample data
    print("\n--- First Bill ---")
    first_bill = bills[0]
    print(f"ID: {first_bill['LegislationId']}")
    print(f"Number: {first_bill['LegislationNumber']}")
    print(f"Sponsor: {first_bill['Sponsor']}")
    print(f"Title: {first_bill['LongTitle'][:100]}...")
    
    print("\n--- Last Bill ---")
    last_bill = bills[-1]
    print(f"ID: {last_bill['LegislationId']}")
    print(f"Number: {last_bill['LegislationNumber']}")
    print(f"Sponsor: {last_bill['Sponsor']}")