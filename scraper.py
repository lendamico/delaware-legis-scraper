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
            self.spreadsheet = self.gc.open(spreadsheet_name)
            self.sheet = self.spreadsheet.sheet1
            print(f"Opened existing spreadsheet: {spreadsheet_name}")
        except gspread.SpreadsheetNotFound:
            self.spreadsheet = self.gc.create(spreadsheet_name)
            self.sheet = self.spreadsheet.sheet1
            print(f"Created new spreadsheet: {spreadsheet_name}")
    
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
    
    def get_legislation_type_name(self, type_id):
        """Convert legislation type ID to human-readable name"""
        type_mapping = {
            1: "Bill",
            2: "Resolution",
            3: "Concurrent Resolution",
            4: "Joint Resolution",
            5: "Amendment",
            6: "Substitute"
        }
        return type_mapping.get(type_id, f"Unknown ({type_id})")
    
    def transform_bill(self, bill):
        """Transform API response into sheet-ready format"""
        bill_number = bill.get("LegislationNumber")
        legislation_id = bill.get("LegislationId")
        parent_bill = bill.get("SubstituteParentLegislationDisplayCode") or ""
        amendment_parent = bill.get("AmendmentParentLegislationDisplayCode") or ""
        legislation_display_code = bill.get("LegislationDisplayCode")
        
        # Determine Sort By value
        if parent_bill:
            sort_by = parent_bill
        elif amendment_parent:
            sort_by = amendment_parent
        else:
            sort_by = bill_number
        
        # Normalize the Sort By value for proper sorting (e.g., HB 13 -> HB 013)
        sort_by_normalized = self.normalize_bill_number(sort_by)
        
        # Create clickable link using Google Sheets HYPERLINK formula
        bill_url = f"https://legis.delaware.gov/BillDetail?LegislationId={legislation_id}"
        bill_link = f'=HYPERLINK("{bill_url}", "{legislation_display_code}")'
        
        return {
            "LegislationId": legislation_id,
            "SortBy": sort_by_normalized,
            "BillNumber": bill_number,
            "DisplayCode": bill_link,
            "Type": self.get_legislation_type_name(bill.get("LegislationTypeId")),
            "Chamber": bill.get("ChamberName"),
            "Sponsor": bill.get("Sponsor"),
            "ShortTitle": bill.get("ShortTitle") or "",
            "LongTitle": bill.get("LongTitle") or "",
            "Synopsis": bill.get("Synopsis") or "",
            "Status": bill.get("StatusName"),
            "IntroducedDate": self.parse_json_date(bill.get("IntroductionDateTime")),
            "LastStatusDate": self.parse_json_date(bill.get("LegislationStatusDateTime")),
            "HasAmendments": bill.get("HasAmendments"),
            "ParentBill": parent_bill,
            "AmendmentParent": amendment_parent
        }
    
    def normalize_bill_number(self, bill_number):
        """Normalize bill number for sorting (e.g., HB 13 -> HB 013)"""
        if not bill_number:
            return ""
        
        import re
        # Match pattern like "HB 13" or "SA 2" or "HS 1 for HB 100"
        match = re.match(r'^([A-Z]+)\s+(\d+)', bill_number)
        
        if match:
            prefix = match.group(1)  # e.g., "HB", "SA", "HS"
            number = match.group(2)  # e.g., "13", "2", "1"
            remainder = bill_number[match.end():]  # Everything after the number
            
            # Pad number to 3 digits
            padded_number = number.zfill(3)
            
            return f"{prefix} {padded_number}{remainder}"
        
        # If no match, return original
        return bill_number
    
    def get_existing_bills(self):
        """Get all existing bills from the sheet as a dictionary"""
        try:
            # Get all values
            all_values = self.sheet.get_all_values()
            
            # If empty or only headers, return empty dict
            if len(all_values) <= 1:
                return {}
            
            # Get headers and find LegislationId column
            headers = all_values[0]
            if "LegislationId" not in headers:
                return {}
            
            id_col_index = headers.index("LegislationId")
            
            # Build dictionary: {LegislationId: (row_number, row_data_dict)}
            existing_bills = {}
            for row_num, row in enumerate(all_values[1:], start=2):  # Start at 2 (row 1 is headers)
                if len(row) > id_col_index and row[id_col_index]:
                    leg_id = str(row[id_col_index])
                    
                    # Convert row to dictionary
                    row_dict = {}
                    for i, header in enumerate(headers):
                        row_dict[header] = row[i] if i < len(row) else ""
                    
                    existing_bills[leg_id] = (row_num, row_dict)
            
            return existing_bills
        
        except Exception as e:
            print(f"Error getting existing bills: {e}")
            return {}
    
    def write_to_sheet(self, bills, existing_bills):
        """Write bill data to Google Sheet efficiently - add new and update changed bills"""
        # Define column headers in desired order
        headers = [
            "LegislationId", "DisplayCode", "SortBy", "ShortTitle",
            "LongTitle", "Synopsis", "Type", "IntroducedDate",
            "Sponsor", "Chamber", "Status", "LastStatusDate",
            "HasAmendments", "ParentBill", "AmendmentParent"
        ]
        
        # Check if sheet is empty
        all_values = self.sheet.get_all_values()
        
        if not all_values:
            # Write headers
            self.sheet.append_row(headers)
            print("Created headers")
        
        # Separate new bills from existing bills
        new_bills = []
        bills_to_update = []
        
        for bill in bills:
            leg_id = str(bill["LegislationId"])
            
            if leg_id not in existing_bills:
                # Brand new bill
                new_bills.append(bill)
            else:
                # Bill exists - check if data has changed
                row_num, existing_data = existing_bills[leg_id]
                
                # Compare data (skip DisplayCode since it's a formula)
                has_changes = False
                for header in headers:
                    if header == "DisplayCode":
                        continue  # Skip formula comparison
                    
                    new_value = str(bill.get(header, ""))
                    old_value = str(existing_data.get(header, ""))
                    
                    if new_value != old_value:
                        has_changes = True
                        break
                
                if has_changes:
                    bills_to_update.append((row_num, bill))
        
        # Append new bills
        if new_bills:
            rows = []
            for bill in new_bills:
                row = [bill.get(header, "") for header in headers]
                rows.append(row)
            
            self.sheet.append_rows(rows, value_input_option='USER_ENTERED')
            print(f"✓ Added {len(rows)} new bills")
        else:
            print("No new bills to add")
        
        # Update existing bills
        if bills_to_update:
            for row_num, bill in bills_to_update:
                row = [bill.get(header, "") for header in headers]
                
                # Update the entire row
                range_name = f"A{row_num}:{self._col_letter(len(headers))}{row_num}"
                self.sheet.update(range_name, [row], value_input_option='USER_ENTERED')
            
            print(f"✓ Updated {len(bills_to_update)} existing bills")
        else:
            print("No bills needed updates")
    
    def _col_letter(self, col_num):
        """Convert column number to letter (1=A, 2=B, ..., 27=AA)"""
        result = ""
        while col_num > 0:
            col_num -= 1
            result = chr(col_num % 26 + ord('A')) + result
            col_num //= 26
        return result
    
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
        
        # Get existing bills
        print("Checking for existing bills in sheet...")
        existing_bills = self.get_existing_bills()
        print(f"Found {len(existing_bills)} existing bills")
        
        # Write to sheet
        print("Writing to Google Sheet...")
        self.write_to_sheet(transformed_bills, existing_bills)
        
        print(f"\nScraper completed at {datetime.now()}")
        print(f"Total bills processed: {len(bills)}")


if __name__ == "__main__":
    # Get credentials from environment variable or file path
    service_account = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', 'service-account.json')
    
    # If it's a JSON string (from GitHub secrets), write to temp file
    if service_account.startswith('{'):
        with open('/tmp/service-account.json', 'w') as f:
            f.write(service_account)
        service_account = '/tmp/service-account.json'
    
    spreadsheet_name = "DE WFP Bill Tracker GA 153"
    
    scraper = DelawareLegislationScraper(service_account, spreadsheet_name)
    scraper.run()