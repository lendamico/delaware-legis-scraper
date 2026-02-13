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
            "HasAmendments": "TRUE" if bill.get("HasAmendments") else "FALSE",  # Convert to uppercase to match Sheets
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
            
            print(f"Sheet has {len(all_values)} rows total")
            
            # If empty, return empty dict
            if len(all_values) == 0:
                print("Sheet is completely empty")
                return {}
            
            # If only headers, return empty dict
            if len(all_values) == 1:
                print("Sheet has only headers")
                return {}
            
            # Get headers and find LegislationId column
            headers = all_values[0]
            print(f"Headers: {headers}")
            
            # Look for "Legislation ID" (with space) not "LegislationId"
            if "Legislation ID" not in headers:
                print("WARNING: 'Legislation ID' column not found!")
                print(f"Available columns: {headers}")
                return {}
            
            id_col_index = headers.index("Legislation ID")
            print(f"'Legislation ID' is in column {id_col_index}")
            
            # Debug: show first few values in that column
            print(f"\nFirst 5 values in 'Legislation ID' column:")
            for i, row in enumerate(all_values[1:6], start=2):
                if len(row) > id_col_index:
                    print(f"  Row {i}: '{row[id_col_index]}'")
                else:
                    print(f"  Row {i}: [row too short, only {len(row)} columns]")
            
            # Build dictionary: {LegislationId: (row_number, row_data_dict)}
            existing_bills = {}
            for row_num, row in enumerate(all_values[1:], start=2):  # Start at 2 (row 1 is headers)
                if len(row) > id_col_index and row[id_col_index]:
                    leg_id = str(row[id_col_index]).strip()  # Add .strip() to remove whitespace
                    
                    if leg_id:  # Only add if not empty after stripping
                        # Convert row to dictionary
                        row_dict = {}
                        for i, header in enumerate(headers):
                            row_dict[header] = row[i] if i < len(row) else ""
                        
                        existing_bills[leg_id] = (row_num, row_dict)
            
            print(f"\nFound {len(existing_bills)} existing bills")
            return existing_bills
        
        except Exception as e:
            print(f"ERROR in get_existing_bills: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def write_to_sheet(self, bills, existing_bills):
        """Write bill data to Google Sheet efficiently - add new and update changed bills"""
        print(f"\n=== WRITE_TO_SHEET DEBUG ===")
        print(f"Received {len(bills)} bills to process")
        print(f"Existing bills dict has {len(existing_bills)} entries")
        
        # Define column headers matching the existing Google Sheet
        # Map from our internal keys to the sheet's column names
        header_mapping = {
            "LegislationId": "Legislation ID",
            "DisplayCode": "Bill Number",  # This will be the hyperlink
            "SortBy": "Sort By",
            "ShortTitle": "Short Title",
            "LongTitle": "Long Title",
            "Synopsis": "Synopsis",
            "Type": "Type",
            "IntroducedDate": "Introduced",
            "Sponsor": "Primary Sponsor",
            "Chamber": "Chamber",
            "Status": "Status",
            "LastStatusDate": "As of",
            "HasAmendments": "Has Amendments",
            "ParentBill": "Parent Bill",
            "AmendmentParent": "Amendment Parent"
        }
        
        # Internal keys in the order they should appear
        internal_keys = [
            "LegislationId", "DisplayCode", "SortBy", "ShortTitle",
            "LongTitle", "Synopsis", "Type", "IntroducedDate",
            "Sponsor", "Chamber", "Status", "LastStatusDate",
            "HasAmendments", "ParentBill", "AmendmentParent"
        ]
        
        # Sheet column names in the same order
        headers = [header_mapping[key] for key in internal_keys]
        
        # Check if sheet is empty
        all_values = self.sheet.get_all_values()
        print(f"Sheet currently has {len(all_values)} rows")
        
        if not all_values:
            # Write headers
            print("Sheet is empty, writing headers...")
            self.sheet.append_row(headers)
            print("✓ Headers written")
            all_values = [headers]  # Update all_values so we know headers exist
        
        # Separate new bills from existing bills
        new_bills = []
        bills_to_update = []
        
        print(f"\nCategorizing {len(bills)} bills...")
        for i, bill in enumerate(bills):
            leg_id = str(bill["LegislationId"]).strip()
            
            if i < 3:  # Debug first 3 bills
                print(f"\nBill {i+1}: LegislationId = '{leg_id}'")
                print(f"  Is in existing_bills? {leg_id in existing_bills}")
            
            if leg_id not in existing_bills:
                # Brand new bill
                new_bills.append(bill)
                if i < 3:
                    print(f"  -> Categorized as NEW")
            else:
                # Bill exists - check if data has changed
                row_num, existing_data = existing_bills[leg_id]
                
                if i < 3:
                    print(f"  -> Found in existing (row {row_num})")
                
                # Compare data (skip DisplayCode/Bill Number since it's a formula that may not match)
                has_changes = False
                changes_found = []
                for internal_key in internal_keys:
                    sheet_header = header_mapping[internal_key]
                    
                    # Skip DisplayCode - it's a HYPERLINK formula that won't match plain text
                    # Skip BillNumber - it's derived from LegislationDisplayCode
                    if internal_key in ["DisplayCode", "BillNumber"]:
                        continue
                    
                    new_value = str(bill.get(internal_key, "")).strip()
                    old_value = str(existing_data.get(sheet_header, "")).strip()
                    
                    if new_value != old_value:
                        has_changes = True
                        changes_found.append(f"{sheet_header}: '{old_value}' -> '{new_value}'")
                
                if has_changes:
                    bills_to_update.append((row_num, bill))
                    if i < 3:
                        print(f"  -> Categorized as UPDATE")
                        for change in changes_found[:3]:  # Show first 3 changes
                            print(f"     {change}")
                else:
                    if i < 3:
                        print(f"  -> No changes, skipping")
        
        print(f"\n=== CATEGORIZATION COMPLETE ===")
        print(f"New bills: {len(new_bills)}")
        print(f"Bills to update: {len(bills_to_update)}")
        print(f"Existing (unchanged): {len(existing_bills) - len(bills_to_update)}")
        
        # Append new bills
        if new_bills:
            print(f"\n=== APPENDING {len(new_bills)} NEW BILLS ===")
            rows = []
            for bill in new_bills:
                # Build row using internal keys in correct order
                row = [bill.get(internal_key, "") for internal_key in internal_keys]
                rows.append(row)
            
            print(f"First new bill data: {rows[0][:3]}...")  # Show first 3 columns
            
            # Use batch_update for better performance
            try:
                print("Calling sheet.append_rows()...")
                
                # Calculate the starting row (after existing data)
                current_rows = len(all_values)
                start_row = current_rows + 1
                end_col = self._col_letter(len(internal_keys))
                range_name = f"A{start_row}:{end_col}"
                
                print(f"Appending to range: {range_name}")
                
                # Use update instead of append_rows to control exact location
                result = self.sheet.update(values=rows, range_name=range_name, value_input_option='USER_ENTERED')
                print(f"update() result: {result}")
                print(f"✓ Added {len(rows)} new bills")
            except Exception as e:
                print(f"ERROR appending rows: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("\n=== No new bills to add ===")
        
        # Update existing bills (batch them for efficiency)
        if bills_to_update:
            print(f"\n=== UPDATING {len(bills_to_update)} BILLS ===")
            try:
                # Batch updates to avoid API quota (max 60 writes per minute)
                batch_size = 50  # Update 50 rows at a time
                total_batches = (len(bills_to_update) + batch_size - 1) // batch_size
                
                for batch_num in range(total_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min((batch_num + 1) * batch_size, len(bills_to_update))
                    batch = bills_to_update[start_idx:end_idx]
                    
                    print(f"\nBatch {batch_num + 1}/{total_batches}: Updating rows {start_idx + 1} to {end_idx}...")
                    
                    # Build batch update request
                    batch_data = []
                    for row_num, bill in batch:
                        row = [bill.get(internal_key, "") for internal_key in internal_keys]
                        end_col = self._col_letter(len(internal_keys))
                        range_name = f"A{row_num}:{end_col}{row_num}"
                        batch_data.append({
                            'range': range_name,
                            'values': [row]
                        })
                    
                    # Send batch update
                    self.sheet.batch_update(batch_data, value_input_option='USER_ENTERED')
                    print(f"  ✓ Updated {len(batch)} rows")
                    
                    # Rate limiting: sleep between batches (except last one)
                    if batch_num < total_batches - 1:
                        print(f"  Sleeping 2 seconds to avoid rate limit...")
                        time.sleep(2)
                
                print(f"\n✓ Updated {len(bills_to_update)} existing bills")
            except Exception as e:
                print(f"ERROR updating rows: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("\n=== No bills needed updates ===")
    
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
        print(f"Spreadsheet URL: {self.spreadsheet.url}")
        
        # Fetch all bills
        print("\n=== Fetching bills from API ===")
        bills = self.fetch_all_bills()
        print(f"Fetched {len(bills)} bills")
        
        # Transform bills
        print("\n=== Transforming bill data ===")
        transformed_bills = [self.transform_bill(bill) for bill in bills]
        print(f"Transformed {len(transformed_bills)} bills")
        
        # Get existing bills
        print("\n=== Checking for existing bills in sheet ===")
        existing_bills = self.get_existing_bills()
        print(f"Found {len(existing_bills)} existing bills in sheet")
        
        # Write to sheet
        print("\n=== Writing to Google Sheet ===")
        self.write_to_sheet(transformed_bills, existing_bills)
        
        print(f"\n=== Scraper completed at {datetime.now()} ===")
        print(f"Spreadsheet URL: {self.spreadsheet.url}")
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
