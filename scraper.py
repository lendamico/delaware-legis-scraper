import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import os
import math

class DelawareLegislationScraper:
    def __init__(self, service_account_path, spreadsheet_name):
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
    
    def fetch_all_bills(self, ga_id=153, page_size=20):
        # Implementation from 3.1
        pass
    
    def parse_json_date(self, json_date):
        # Implementation from 3.2
        pass
    
    def transform_bill(self, bill):
        # Implementation from 3.3
        pass
    
    def get_existing_ids(self):
        # Implementation from 3.4
        pass
    
    def write_to_sheet(self, bills, existing_ids):
        # Implementation from 3.5
        pass
    touch
    def run(self):
        print(f"Starting scraper at {datetime.now()}")
        
        # Fetch all bills
        print("Fetching bills from API...")
        bills = self.fetch_all_bills()
        print(f"Fetched {len(bills)} bills")
        
        # Transform bills
        print("Transforming bill data...")
        transformed_bills = [self.transform_bill(bill) for bill in bills]
        
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
    service_account = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', 'service-account.json')
    
    # If it's a JSON string (from GitHub secrets), write to temp file
    if service_account.startswith('{'):
        with open('/tmp/service-account.json', 'w') as f:
            f.write(service_account)
        service_account = '/tmp/service-account.json'
    
    spreadsheet_name = "Delaware Legislation - GA 153"
    
    scraper = DelawareLegislationScraper(service_account, spreadsheet_name)
    scraper.run()