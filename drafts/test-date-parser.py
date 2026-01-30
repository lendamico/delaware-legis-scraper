from datetime import datetime

def parse_json_date(json_date):
    """Convert JSON date format to readable format"""
    if not json_date or json_date == "":
        return ""
    
    try:
        # Extract timestamp from "/Date(1747153160257)/"
        timestamp_str = json_date.strip("/Date()")
        timestamp = int(timestamp_str)
        
        # Convert milliseconds to seconds
        timestamp_seconds = timestamp / 1000
        
        # Convert to datetime
        dt = datetime.fromtimestamp(timestamp_seconds)
        
        # Format as YYYY-MM-DD
        return dt.strftime("%Y-%m-%d")
    
    except Exception as e:
        print(f"Error parsing date '{json_date}': {e}")
        return ""


# Test it with real data from the API
if __name__ == "__main__":
    # Test cases from actual API responses
    test_dates = [
        "/Date(1747153160257)/",  # Normal date
        "/Date(1736436429670)/",  # Another normal date
        "/Date(1769538154717)/",  # Future date
        "",                        # Empty string
        None,                      # None value
    ]
    
    print("Testing date parser:\n")
    for date in test_dates:
        result = parse_json_date(date)
        print(f"Input:  {date}")
        print(f"Output: {result}")
        print()
    
    # Test with real bill data
    print("\n--- Testing with real API data ---")
    import requests
    
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
        "pageSize": 5,  # Just get 5 bills for testing
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
    
    print("\nParsing dates from first 5 bills:")
    for bill in result['Data']:
        bill_num = bill['LegislationNumber']
        intro_date_raw = bill.get('IntroductionDateTime', '')
        status_date_raw = bill.get('LegislationStatusDateTime', '')
        
        intro_date = parse_json_date(intro_date_raw)
        status_date = parse_json_date(status_date_raw)
        
        print(f"\n{bill_num}:")
        print(f"  Introduced: {intro_date}")
        print(f"  Last Status: {status_date}")