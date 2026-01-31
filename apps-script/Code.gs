/**
 * Bill Tracker - Export to Google Doc
 * 
 * Installation Instructions:
 * 1. In your Google Sheet, go to Extensions > Apps Script
 * 2. Delete any existing code in the editor
 * 3. Paste this entire script
 * 4. Click the disk icon to save
 * 5. Name the project "Bill Export Script"
 * 6. Click on "Project Settings" (gear icon on left sidebar)
 * 7. Check "Show 'appsscript.json' manifest file in editor"
 * 8. Go back to Editor and click on appsscript.json
 * 9. Replace its contents with the manifest shown below
 * 10. Refresh your Google Sheet
 * 11. You should see a new "Bill Tracker" menu at the top
 * 12. First time you run it, Google will ask for permissions - click "Allow"
 * 
 * Required appsscript.json manifest:
 * {
 *   "timeZone": "America/New_York",
 *   "dependencies": {},
 *   "exceptionLogging": "STACKDRIVER",
 *   "runtimeVersion": "V8",
 *   "oauthScopes": [
 *     "https://www.googleapis.com/auth/spreadsheets.currentonly",
 *     "https://www.googleapis.com/auth/documents",
 *     "https://www.googleapis.com/auth/drive.readonly",
 *     "https://www.googleapis.com/auth/drive.file",
 *     "https://www.googleapis.com/auth/script.container.ui"
 *   ]
 * }
 */

// Configuration - Color mapping for Good/Bad scores
const COLORS = {
  'Good': '#d4edda',                    // Light green
  'Bad': '#f8d7da',                     // Light red
  'Neutral': '#fff3cd',                 // Light yellow
  'Needs more discussion': '#ffe5cc',   // Light orange
  'Unknown': '#e9ecef'                  // Light gray
};

// Create custom menu when spreadsheet opens
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Bill Tracker')
    .addItem('Export Selected Bills', 'showExportDialog')
    .addItem('❌ Export Bills from Meeting Notice', 'showMeetingExportDialog')
    .addToUi();
}

// Show dialog to choose create new or append
function showExportDialog() {
  const html = HtmlService.createHtmlOutputFromFile('ExportDialog')
    .setWidth(400)
    .setHeight(200);
  SpreadsheetApp.getUi().showModalDialog(html, 'Export Bills to Google Doc');
}

// Show dialog for meeting export
function showMeetingExportDialog() {
  const html = HtmlService.createHtmlOutputFromFile('MeetingExportDialog')
    .setWidth(450)
    .setHeight(250);
  SpreadsheetApp.getUi().showModalDialog(html, 'Export Meeting Bills to Google Doc');
}

// Create new Google Doc with exported bills
function createNewDoc() {
  try {
    const bills = getSelectedBills();
    
    if (bills.length === 0) {
      SpreadsheetApp.getUi().alert('No bills selected', 
        'Please check the boxes next to the bills you want to export.', 
        SpreadsheetApp.getUi().ButtonSet.OK);
      return { success: false };
    }
    
    // Create new doc with timestamp
    const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
    const docName = `Bill Briefings - ${timestamp}`;
    const doc = DocumentApp.create(docName);
    const body = doc.getBody();
    
    // Add content
    writeBillsToDoc(body, bills, false);
    
    // Return success with doc URL
    return {
      success: true,
      docUrl: doc.getUrl(),
      docName: docName,
      billCount: bills.length
    };
    
  } catch (error) {
    Logger.log('Error in createNewDoc: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Append to existing Google Doc
function appendToDoc(docId) {
  try {
    const bills = getSelectedBills();
    
    if (bills.length === 0) {
      SpreadsheetApp.getUi().alert('No bills selected', 
        'Please check the boxes next to the bills you want to export.', 
        SpreadsheetApp.getUi().ButtonSet.OK);
      return { success: false };
    }
    
    // Open existing doc
    const doc = DocumentApp.openById(docId);
    const body = doc.getBody();
    
    // Add content
    writeBillsToDoc(body, bills, true);
    
    // Return success
    return {
      success: true,
      docUrl: doc.getUrl(),
      docName: doc.getName(),
      billCount: bills.length
    };
    
  } catch (error) {
    Logger.log('Error in appendToDoc: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Get selected bills from the sheet
function getSelectedBills() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  
  // Find column indices
  const exportCol = headers.indexOf('Export');
  const displayCol = headers.indexOf('Bill Number');
  const sponsorCol = headers.indexOf('Primary Sponsor');
  const shortTitleCol = headers.indexOf('ShortTitle');
  const longTitleCol = headers.indexOf('LongTitle');
  const briefingCol = headers.indexOf('Briefing Text');
  const goodBadCol = headers.indexOf('Good/Bad');
  
  // Validate required columns exist
  if (exportCol === -1) {
    throw new Error('Missing "Export" column. Please add a column named "Export" for checkboxes.');
  }
  if (displayCol === -1 || sponsorCol === -1 || briefingCol === -1) {
    throw new Error('Missing required columns (Bill Number, Primary Sponsor, or Briefing Text).');
  }
  
  const bills = [];
  
  // Loop through rows (skip header)
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    
    // Check if Export checkbox is checked
    if (row[exportCol] === true) {
      // Extract display code text (handle HYPERLINK formula)
      let displayCode = row[displayCol];
      if (typeof displayCode === 'string' && displayCode.includes('HYPERLINK')) {
        // Extract the display text from =HYPERLINK("url", "text")
        const match = displayCode.match(/HYPERLINK\(".*?",\s*"(.*?)"\)/);
        if (match) {
          displayCode = match[1];
        }
      }
      
      bills.push({
        displayCode: displayCode || '',
        sponsor: row[sponsorCol] || '',
        shortTitle: row[shortTitleCol] || '',
        longTitle: row[longTitleCol] || '',
        briefing: row[briefingCol] || '',
        goodBad: row[goodBadCol] || 'Unknown'
      });
    }
  }
  
  return bills;
}

// Write bills to document body
function writeBillsToDoc(body, bills, isAppending) {
  // If appending, add separator
  if (isAppending && body.getText().trim().length > 0) {
    body.appendParagraph('\n' + '='.repeat(80));
    body.appendParagraph('Exported: ' + new Date().toLocaleString());
    body.appendParagraph('='.repeat(80) + '\n');
  }
  
  // Add each bill
  bills.forEach((bill, index) => {
    // Get the color for this bill
    const color = COLORS[bill.goodBad] || COLORS['Unknown'];
    
    // Create the formatted line: [Bill Display] (Sponsor):
    const headerPara = body.appendParagraph('');
    
    // Add bill display code in bold
    const displayText = headerPara.appendText(bill.displayCode);
    displayText.setBold(true);
    
    // Add sponsor in italics within parentheses
    headerPara.appendText(' (');
    const sponsorText = headerPara.appendText(bill.sponsor);
    sponsorText.setItalic(true);
    headerPara.appendText('):');
    
    // Apply background color to header
    headerPara.setBackgroundColor(color);
    
    // Add briefing text on new line if it exists
    if (bill.briefing && bill.briefing.trim() !== '') {
      const briefingPara = body.appendParagraph(bill.briefing);
      
      // Apply same background color to briefing
      briefingPara.setBackgroundColor(color);
      
      // Add some padding with paragraph spacing
      briefingPara.setSpacingBefore(3);
      briefingPara.setSpacingAfter(8);
    }
    
    // Add spacing between bills
    if (index < bills.length - 1) {
      body.appendParagraph('');
    }
  });
}

// Get OAuth token for Drive Picker (required for file picker)
function getOAuthToken() {
  return ScriptApp.getOAuthToken();
}

// Fetch meeting details and bills from Delaware API
function fetchMeetingData(meetingUrl) {
  try {
    // Extract committee meeting ID from URL
    const match = meetingUrl.match(/MeetingNotice\/(\d+)/);
    if (!match) {
      throw new Error('Invalid meeting URL. Expected format: https://legis.delaware.gov/MeetingNotice/33615');
    }
    
    const committeeMeetingId = match[1];
    
    // Fetch meeting items (bills)
    const itemsUrl = 'https://legis.delaware.gov/json/MeetingNotice/GetCommitteeMeetingItems';
    const itemsPayload = `sort=&group=&filter=`;
    const itemsOptions = {
      method: 'post',
      contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
      headers: {
        'Accept': '*/*',
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://legis.delaware.gov/'
      },
      payload: itemsPayload,
      muteHttpExceptions: true
    };
    
    const itemsResponse = UrlFetchApp.fetch(
      `${itemsUrl}?committeeMeetingId=${committeeMeetingId}`, 
      itemsOptions
    );
    const itemsData = JSON.parse(itemsResponse.getContentText());
    
    if (!itemsData.Data || itemsData.Data.length === 0) {
      throw new Error('No bills found for this meeting.');
    }
    
    // Get committee info from first item
    const firstItem = itemsData.Data[0];
    const committeeId = firstItem.CommitteeId;
    const committeeName = firstItem.CommitteeName;
    const chamberType = firstItem.CommitteeTypeShortCode || 'House'; // Assume House if not specified
    
    // Try to fetch from upcoming meetings first
    let meetingDateTime = null;
    const meetingsPayload = `sort=&group=&filter=`;
    const meetingsOptions = {
      method: 'post',
      contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
      headers: {
        'Accept': '*/*',
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://legis.delaware.gov/'
      },
      payload: meetingsPayload,
      muteHttpExceptions: true
    };
    
    // Try upcoming meetings
    const upcomingUrl = 'https://legis.delaware.gov/json/Committee/GetCommitteeUpcomingMeetings';
    const upcomingResponse = UrlFetchApp.fetch(
      `${upcomingUrl}?committeeId=${committeeId}`, 
      meetingsOptions
    );
    const upcomingData = JSON.parse(upcomingResponse.getContentText());
    
    if (upcomingData.Data) {
      const meeting = upcomingData.Data.find(m => m.CommitteeMeetingId == committeeMeetingId);
      if (meeting) {
        meetingDateTime = meeting.MeetingDateTime;
      }
    }
    
    // If not found in upcoming, try past meetings
    if (!meetingDateTime) {
      const pastUrl = 'https://legis.delaware.gov/json/Committee/GetCommitteePastMeetings';
      const pastResponse = UrlFetchApp.fetch(
        `${pastUrl}?committeeId=${committeeId}`, 
        meetingsOptions
      );
      const pastData = JSON.parse(pastResponse.getContentText());
      
      if (pastData.Data) {
        const meeting = pastData.Data.find(m => m.CommitteeMeetingId == committeeMeetingId);
        if (meeting) {
          meetingDateTime = meeting.MeetingDateTime;
        }
      }
    }
    
    // Extract bill info
    const bills = itemsData.Data.map(item => ({
      legislationId: item.LegislationId,
      displayCode: item.LegislationDisplayText || item.LegislationDisplayCode,
      sponsor: item.PrimarySponsorShortName,
      billUrl: `https://legis.delaware.gov/BillDetail?LegislationId=${item.LegislationId}`
    }));
    
    return {
      success: true,
      committeeMeetingId: committeeMeetingId,
      committeeName: `${chamberType} ${committeeName}`,
      meetingDateTime: meetingDateTime,
      meetingUrl: meetingUrl,
      bills: bills
    };
    
  } catch (error) {
    Logger.log('Error in fetchMeetingData: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Create new doc with meeting bills
function createNewDocWithMeeting(meetingUrl) {
  try {
    const meetingData = fetchMeetingData(meetingUrl);
    
    if (!meetingData.success) {
      return { success: false, error: meetingData.error };
    }
    
    // Get bill details from tracker
    const billsWithDetails = getBillDetailsForMeeting(meetingData.bills);
    
    // Create new doc
    const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
    const docName = `${meetingData.committeeName} - ${timestamp}`;
    const doc = DocumentApp.create(docName);
    const body = doc.getBody();
    
    // Write meeting content
    writeMeetingToDoc(body, meetingData, billsWithDetails, false);
    
    return {
      success: true,
      docUrl: doc.getUrl(),
      docName: docName,
      billCount: billsWithDetails.length
    };
    
  } catch (error) {
    Logger.log('Error in createNewDocWithMeeting: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Append meeting bills to existing doc
function appendToDocWithMeeting(docId, meetingUrl) {
  try {
    const meetingData = fetchMeetingData(meetingUrl);
    
    if (!meetingData.success) {
      return { success: false, error: meetingData.error };
    }
    
    // Get bill details from tracker
    const billsWithDetails = getBillDetailsForMeeting(meetingData.bills);
    
    // Open existing doc
    const doc = DocumentApp.openById(docId);
    const body = doc.getBody();
    
    // Write meeting content
    writeMeetingToDoc(body, meetingData, billsWithDetails, true);
    
    return {
      success: true,
      docUrl: doc.getUrl(),
      docName: doc.getName(),
      billCount: billsWithDetails.length
    };
    
  } catch (error) {
    Logger.log('Error in appendToDocWithMeeting: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Get bill details from tracker sheet
function getBillDetailsForMeeting(meetingBills) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  
  // Find column indices
  const legIdCol = headers.indexOf('LegislationId');
  const briefingCol = headers.indexOf('Briefing Text');
  const goodBadCol = headers.indexOf('Good/Bad');
  
  const billsWithDetails = [];
  
  // For each meeting bill, try to find it in the tracker
  meetingBills.forEach(meetingBill => {
    let found = false;
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      
      if (row[legIdCol] == meetingBill.legislationId) {
        // Found in tracker
        billsWithDetails.push({
          displayCode: meetingBill.displayCode,
          sponsor: meetingBill.sponsor,
          billUrl: meetingBill.billUrl,
          briefing: row[briefingCol] || '',
          goodBad: row[goodBadCol] || 'Unknown',
          tracked: true
        });
        found = true;
        break;
      }
    }
    
    if (!found) {
      // Not in tracker
      billsWithDetails.push({
        displayCode: meetingBill.displayCode,
        sponsor: meetingBill.sponsor,
        billUrl: meetingBill.billUrl,
        briefing: '',
        goodBad: 'Unknown',
        tracked: false
      });
    }
  });
  
  return billsWithDetails;
}

// Write meeting content to doc
function writeMeetingToDoc(body, meetingData, bills, isAppending) {
  // If appending, add separator
  if (isAppending && body.getText().trim().length > 0) {
    body.appendParagraph('\n' + '='.repeat(80) + '\n');
  }
  
  // Add committee name as heading (larger, bold)
  const committeePara = body.appendParagraph(meetingData.committeeName);
  committeePara.setHeading(DocumentApp.ParagraphHeading.HEADING1);
  
  // Add meeting date/time with link
  if (meetingData.meetingDateTime) {
    const datePara = body.appendParagraph('');
    const dateLink = datePara.appendText(meetingData.meetingDateTime);
    dateLink.setLinkUrl(meetingData.meetingUrl);
    dateLink.setUnderline(true);
    dateLink.setForegroundColor('#1155cc'); // Blue link color
  }
  
  body.appendParagraph(''); // Spacing
  
  // Add each bill
  bills.forEach((bill, index) => {
    // Get color for this bill
    const color = COLORS[bill.goodBad] || COLORS['Unknown'];
    
    // Create bullet point with bill info
    const billPara = body.appendListItem('');
    billPara.setGlyphType(DocumentApp.GlyphType.BULLET);
    
    // Add bill display code as link in bold
    const billLink = billPara.appendText(bill.displayCode);
    billLink.setBold(true);
    billLink.setLinkUrl(bill.billUrl);
    billLink.setUnderline(true);
    billLink.setForegroundColor('#1155cc');
    
    // Add sponsor in italics
    billPara.appendText(' (');
    const sponsorText = billPara.appendText(bill.sponsor);
    sponsorText.setItalic(true);
    billPara.appendText(')');
    
    // Apply background color
    billPara.setBackgroundColor(color);
    
    // Add briefing as indented sub-item or note if not tracked
    if (!bill.tracked) {
      const notePara = body.appendListItem('(Not tracked in bill tracker)');
      notePara.setNestingLevel(1);
      notePara.setGlyphType(DocumentApp.GlyphType.BULLET);
      notePara.setBackgroundColor(color);
      notePara.setItalic(true);
    } else if (bill.briefing && bill.briefing.trim() !== '') {
      const briefingPara = body.appendListItem(bill.briefing);
      briefingPara.setNestingLevel(1);
      briefingPara.setGlyphType(DocumentApp.GlyphType.BULLET);
      briefingPara.setBackgroundColor(color);
    } else {
      const noBriefingPara = body.appendListItem('(No briefing available)');
      noBriefingPara.setNestingLevel(1);
      noBriefingPara.setGlyphType(DocumentApp.GlyphType.BULLET);
      noBriefingPara.setBackgroundColor(color);
      noBriefingPara.setItalic(true);
    }
  });
}