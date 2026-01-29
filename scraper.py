import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import os
import math

class DelawareLegislationScraper:
    def __init__(self, service_account_path, spreadsheet_name):
        """Initialize the scraper with Google Sheets credentials."""
        # Initialize API settings
        self.api_url = "https://legis.delaware.gov/json/AllLegislation/GetAllLegislation"
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
            "Referer": "https://legis.delaware.gov/AllLegislation",
            "Accept": "*/*"
        }
        
        # Initialize Google Sheets
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
        self.gc = gspread.authorize(creds)
        
        # Open or create spreadsheet
        try:
            self.spreadsheet = self.gc.open("DE WFP Bill Tracker GA 153")
            self.sheet = self.spreadsheet.sheet1
            print(f"Opened existing spreadsheet: DE WFP Bill Tracker GA 153")
        except gspread.SpreadsheetNotFound:
            self.spreadsheet = self.gc.create("DE WFP Bill Tracker GA 153")
            self.sheet = self.spreadsheet.sheet1
            print(f"Created new spreadsheet: DE WFP Bill Tracker GA 153")
    
    def fetch_all_bills(self, ga_id=153, page_size=100):
        """Fetch all bills from GA 153 across multiple pages"""
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
        
        response = requests.post(self.api_url, headers=self.headers, data=data)
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
            
            response = requests.post(self.api_url, headers=self.headers, data=data)
            response.raise_for_status()
            result = response.json()
            
            bills.extend(result['Data'])
            print(f"Got {len(result['Data'])} bills from page {page}")
            
            time.sleep(0.2)  # Rate limiting
        
        print(f"Total bills fetched: {len(bills)}")
        return bills
    
    def parse_json_date(self, json_date):
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
    
    def transform_bill(self, bill):
        """Transform API response into sheet-ready format"""
        return {
            "LegislationId": bill.get("LegislationId"),
            "BillNumber": bill.get("LegislationNumber"),
            "DisplayCode": bill.get("LegislationDisplayCode"),
            "Type": bill.get("LegislationTypeId"),
            "Chamber": bill.get("ChamberName"),
            "Sponsor": bill.get("Sponsor"),
            "SponsorLink": bill.get("LegislatorDetailLink"),
            "ShortTitle": bill.get("ShortTitle") or "",
            "LongTitle": bill.get("LongTitle") or "",
            "Synopsis": bill.get("Synopsis") or "",
            "Status": bill.get("StatusName"),
            "IntroducedDate": self.parse_json_date(bill.get("IntroductionDateTime")),
            "LastStatusDate": self.parse_json_date(bill.get("LegislationStatusDateTime")),
            "HasAmendments": bill.get("HasAmendments"),
            "ParentBill": bill.get("SubstituteParentLegislationDisplayCode") or "",
            "AmendmentParent": bill.get("AmendmentParentLegislationDisplayCode") or ""
        }
    
    def get_existing_ids(self):
        """Get legislation IDs that are already in the sheet"""
        try:
            # Get all values
            all_values = self.sheet.get_all_values()
            
            # If empty or only headers, return empty set
            if len(all_values) <= 1:
                return set()
            
            # Find LegislationId column
            headers = all_values[0]
            if "LegislationId" not in headers:
                return set()
            
            id_col_index = headers.index("LegislationId")
            
            # Extract all IDs (skip header row)
            existing_ids = set()
            for row in all_values[1:]:
                if len(row) > id_col_index and row[id_col_index]:
                    existing_ids.add(str(row[id_col_index]))
            
            return existing_ids
        
        except Exception as e:
            print(f"Error getting existing IDs: {e}")
            return set()
    
    def write_to_sheet(self, bills, existing_ids):
        """Write bill data to Google Sheet efficiently"""
        # Define column headers
        headers = [
            "LegislationId", "BillNumber", "DisplayCode", "Type",
            "Chamber", "Sponsor", "SponsorLink", "ShortTitle",
            "LongTitle", "Synopsis", "Status", "IntroducedDate",
            "LastStatusDate", "HasAmendments", "ParentBill", "AmendmentParent"
        ]
        
        # Check if sheet is empty
        all_values = self.sheet.get_all_values()
        
        if not all_values:
            # Write headers
            self.sheet.append_row(headers)
            print("Created headers")
        
        # Filter to only new bills
        new_bills = [
            bill for bill in bills 
            if str(bill["LegislationId"]) not in existing_ids
        ]
        
        if not new_bills:
            print("No new bills to add")
            return
        
        # Convert to rows
        rows = []
        for bill in new_bills:
            row = [bill.get(header, "") for header in headers]
            rows.append(row)
        
        # Batch append
        self.sheet.append_rows(rows)
        print(f"Added {len(rows)} new bills")
    
    def run(self):
        """Main execution method"""
        print(f"Starting scraper at {datetime.now()}")
        
        # Fetch all bills
        print("Fetching bills from API...")
        bills = self.fetch_all_bills()
        print(f"Fetched {len(bills)} bills")
        
        # Transform bills
        print("Transforming bill data...")
        transformed_bills = [self.transform_bill(bill) for bill in bills]
        print(f"Transformed {len(transformed_bills)} bills")
        
        # Get existing IDs
        print("Checking for existing bills in sheet...")
        existing_ids = self.get_existing_ids()
        print(f"Found {len(existing_ids)} existing bills")
        
        # Write to sheet
        print("Writing to Google Sheet...")
        self.write_to_sheet(transformed_bills, existing_ids)
        
        print(f"Scraper completed at {datetime.now()}")
        print(f"Total bills processed: {len(bills)}")


if __name__ == "__main__":
    # Get credentials from environment variable or file path
    service_account = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', 'service-account.json')
    
    # If it's a JSON string (from GitHub secrets), write to temp file
    if service_account.startswith('{'):
        with open('/tmp/service-account.json', 'w') as f:
            f.write(service_account)
        service_account = '/tmp/service-account.json'
    
    spreadsheet_name = "Delaware Legislation - GA 153"
    
    scraper = DelawareLegislationScraper(service_account, spreadsheet_name)
    scraper.run()
