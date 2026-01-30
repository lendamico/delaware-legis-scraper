import requests
import json

url = "https://legis.delaware.gov/json/AllLegislation/GetAllLegislation"
headers = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Referer": "https://legis.delaware.gov/AllLegislation",
    "Accept": "*/*"
}
data = {
    "sort": "",
    "page": 1,
    "pageSize": 10,
    "group": "",
    "filter": "",
    "selectedGA[0]": 153,
    "sponsorName": "",
    "fromIntroDate": "",
    "toIntroDate": "",
    "coSponsorCheck": False
}

response = requests.post(url, headers=headers, data=data)
result = response.json()

# Get first bill and print all keys
first_bill = result['Data'][0]
print("All available fields in bill data:")
print(json.dumps(list(first_bill.keys()), indent=2))

print("\n" + "="*60 + "\n")

# Look specifically for sponsor-related fields
print("Sponsor-related fields:")
for key in first_bill.keys():
    if 'sponsor' in key.lower() or 'co' in key.lower():
        print(f"{key}: {first_bill[key]}")