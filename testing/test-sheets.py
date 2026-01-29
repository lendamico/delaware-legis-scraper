import gspread
from google.oauth2.service_account import Credentials

scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds = Credentials.from_service_account_file('service-account.json', scopes=scopes)
gc = gspread.authorize(creds)

# Create a test spreadsheet
spreadsheet = gc.open("DE WFP Bill Tracker GA 153")
sheet = spreadsheet.sheet1

# Write test data
sheet.update([[
    "LegislationId", "BillNumber", "Title"
], [
    142255, "HB 302", "Test Bill"
]])

print(f"Created spreadsheet: {spreadsheet.url}")