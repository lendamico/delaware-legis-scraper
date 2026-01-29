from datetime import datetime

def parse_json_date(json_date):
    """Convert JSON date format to readable format"""
    if not json_date or json_date == "":
        return ""
    
    try:
        timestamp_str = json_date.strip("/Date()")
        timestamp = int(timestamp_str)
        timestamp_seconds = timestamp / 1000
        dt = datetime.fromtimestamp(timestamp_seconds)
        return dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error parsing date '{json_date}': {e}")
        return ""


def transform_bill(bill):
    """Transform API response into sheet-ready format"""
    return {
        "LegislationId": bill.get("LegislationId"),
        "BillNumber": bill.get("LegislationNumber"),
        "DisplayCode": bill.get("LegislationDisplayCode"),
        "Type": bill.get("LegislationTypeId"),
        "Chamber": bill.get("ChamberName"),
        "Sponsor": bill.get("Sponsor"),
        "SponsorLink": bill.get("LegislatorDetailLink"),
        "ShortTitle": bill.get("ShortTitle") or "",  # Handle None values
        "LongTitle": bill.get("LongTitle") or "",
        "Synopsis": bill.get("Synopsis") or "",
        "Status": bill.get("StatusName"),
        "IntroducedDate": parse_json_date(bill.get("IntroductionDateTime")),
        "LastStatusDate": parse_json_date(bill.get("LegislationStatusDateTime")),
        "HasAmendments": bill.get("HasAmendments"),
        "ParentBill": bill.get("SubstituteParentLegislationDisplayCode") or "",
        "AmendmentParent": bill.get("AmendmentParentLegislationDisplayCode") or ""
    }


# Test it
if __name__ == "__main__":
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
        "pageSize": 3,  # Get 3 bills for testing
        "group": "",
        "filter": "",
        "selectedGA[0]": 153,
        "sponsorName": "",
        "fromIntroDate": "",
        "toIntroDate": "",
        "coSponsorCheck": False
    }
    
    print("Fetching sample bills from API...\n")
    response = requests.post(url, headers=headers, data=data)
    result = response.json()
    
    print(f"Got {len(result['Data'])} bills\n")
    print("=" * 80)
    
    for i, bill in enumerate(result['Data'], 1):
        print(f"\n--- Bill {i}: RAW DATA ---")
        print(f"LegislationId: {bill.get('LegislationId')}")
        print(f"LegislationNumber: {bill.get('LegislationNumber')}")
        print(f"Sponsor: {bill.get('Sponsor')}")
        print(f"ShortTitle: {bill.get('ShortTitle')}")
        print(f"IntroductionDateTime: {bill.get('IntroductionDateTime')}")
        
        print(f"\n--- Bill {i}: TRANSFORMED DATA ---")
        transformed = transform_bill(bill)
        for key, value in transformed.items():
            # Truncate long values for readability
            if isinstance(value, str) and len(value) > 100:
                display_value = value[:100] + "..."
            else:
                display_value = value
            print(f"{key}: {display_value}")
        
        print("\n" + "=" * 80)
    
    # Test with all bills to check for any transformation errors
    print("\n\nTesting transformation on all bills from page 1...")
    data["pageSize"] = 100
    response = requests.post(url, headers=headers, data=data)
    result = response.json()
    
    success_count = 0
    error_count = 0
    
    for bill in result['Data']:
        try:
            transformed = transform_bill(bill)
            # Verify all expected fields are present
            expected_fields = [
                "LegislationId", "BillNumber", "DisplayCode", "Type",
                "Chamber", "Sponsor", "SponsorLink", "ShortTitle",
                "LongTitle", "Synopsis", "Status", "IntroducedDate",
                "LastStatusDate", "HasAmendments", "ParentBill", "AmendmentParent"
            ]
            
            for field in expected_fields:
                if field not in transformed:
                    raise ValueError(f"Missing field: {field}")
            
            success_count += 1
        except Exception as e:
            error_count += 1
            print(f"Error transforming bill {bill.get('LegislationNumber')}: {e}")
    
    print(f"\nTransformation test results:")
    print(f"  ✓ Success: {success_count}")
    print(f"  ✗ Errors: {error_count}")
    
    if error_count == 0:
        print("\n✓ All bills transformed successfully!")
    else:
        print(f"\n⚠ {error_count} bills had transformation errors")