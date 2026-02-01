/* ===========================
   CONFIG
   Color-coding the output based upon Good/Bad status in tracker sheet
=========================== */

const COLORS = {
  'Good': '#d4edda',
  'Bad': '#f8d7da',
  'Neutral': '#fff3cd',
  'Needs more discussion': '#ffe5cc',
  'Unknown': '#e9ecef'
};

/* ===========================
   SAFE FETCH
   Grabbing meeting data from Meeting Notice link
=========================== */

function safeFetchJson(url, options, label) {
  const r = UrlFetchApp.fetch(url, options);
  const code = r.getResponseCode();
  const text = r.getContentText();

  if (code !== 200 || !text || text.trim().startsWith('<')) {
    throw new Error(`${label} failed (HTTP ${code})`);
  }
  return JSON.parse(text);
}

/* ===========================
   UI
   adds button to Google Sheet
=========================== */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🐺 Export')
    .addItem('Export Bills from Meeting Notice link', 'showMeetingExportDialog')
    .addToUi();
}

function showMeetingExportDialog() {
  SpreadsheetApp.getUi().showModalDialog(
    HtmlService.createHtmlOutputFromFile('MeetingExportDialog')
      .setWidth(450)
      .setHeight(300),
    'Export Meeting Bills'
  );
}

/* ===========================
   OAUTH
=========================== */

function getOAuthToken() {
  return ScriptApp.getOAuthToken();
}

/* ===========================
   DATE SCRAPER
   scrape date from meeting notice HTML (since API does not provide it)
=========================== */

function scrapeMeetingDateTimeFromHtml(meetingUrl) {
  const html = UrlFetchApp.fetch(meetingUrl, {
    headers: { 'User-Agent': 'Mozilla/5.0' },
    muteHttpExceptions: true
  }).getContentText();

  if (!html) return '';

  // Find the Date/Time info-value block
  const blockMatch = html.match(
    /Date\/Time:\s*<\/label>\s*<div class="info-value">\s*([\s\S]*?)<\/div>/i
  );

  if (!blockMatch) return '';

  // Clean up whitespace
  const raw = blockMatch[1].replace(/\s+/g, ' ').trim();
  // Example: "6/25/25 1:00 PM"

  const parsed = parseMeetingDateTime(raw);
  return parsed || '';
}

/* ===========================
   DATE PARSER
   Prepend day of week to meeting date/time and wrap in meeting link
=========================== */

function parseMeetingDateTime(raw) {
  // Expected: M/D/YY h:mm AM|PM
  const m = raw.match(
    /^(\d{1,2})\/(\d{1,2})\/(\d{2})\s+(\d{1,2}):(\d{2})\s+(AM|PM)$/i
  );
  if (!m) return '';

  let [, month, day, year, hour, minute, ampm] = m;

  year = Number(year) + 2000;
  hour = Number(hour);
  minute = Number(minute);

  if (ampm.toUpperCase() === 'PM' && hour !== 12) hour += 12;
  if (ampm.toUpperCase() === 'AM' && hour === 12) hour = 0;

  const date = new Date(year, month - 1, day, hour, minute);

  const dayName = Utilities.formatDate(
    date,
    Session.getScriptTimeZone(),
    'EEEE'
  );

  const formatted = Utilities.formatDate(
    date,
    Session.getScriptTimeZone(),
    'M/d/yy h:mm a'
  );

  return `${dayName}, ${formatted}`;
}


/* ===========================
   MEETING FETCH
   Get the bills associated with a meeting notice 
=========================== */

function fetchMeetingData(meetingUrl) {
  let meetingDateTime = '';
  const m = meetingUrl.match(/MeetingNotice\/(\d+)/);
  if (!m) throw new Error('Invalid Meeting Notice URL');

  const meetingId = m[1];

  const opts = {
    method: 'post',
    contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
    headers: {
      'Accept': 'application/json, text/plain, */*',
      'User-Agent': 'Mozilla/5.0',
      'Referer': meetingUrl
    },
    payload: 'sort=&group=&filter=',
    muteHttpExceptions: true
  };

  const items = safeFetchJson(
    `https://legis.delaware.gov/json/MeetingNotice/GetCommitteeMeetingItems?committeeMeetingId=${meetingId}`,
    opts,
    'Meeting items'
  );

  const first = items.Data[0];
  const committeeId = first.CommitteeId;
  
// FINAL fallback: scrape HTML if APIs failed
if (!meetingDateTime) {
  try {
    meetingDateTime = scrapeMeetingDateTimeFromHtml(meetingUrl);
  } catch (_) {}
}

return {
  committeeName: `${first.CommitteeTypeShortCode || 'House'} ${first.CommitteeName}`,
  meetingDateTime,
  meetingUrl,
  bills: items.Data.map(i => ({
    legislationId: i.LegislationId,
    displayCode: i.LegislationDisplayText || i.LegislationDisplayCode,
    sponsor: i.PrimarySponsorShortName,
    billUrl: `https://legis.delaware.gov/BillDetail?LegislationId=${i.LegislationId}`
  }))
};
}

/* ===========================
   MEETING EXPORT
    Create or append to Google Doc with meeting bills
=========================== */

function createNewDocWithMeeting(meetingUrl) {
  try {
    const meeting = fetchMeetingData(meetingUrl);
    const bills = getBillDetailsForMeeting(meeting.bills);

    const ts = Utilities.formatDate(
      new Date(),
      Session.getScriptTimeZone(),
      'yyyy-MM-dd HH:mm'
    );

    const docName = `${meeting.committeeName} - ${ts}`;
    const doc = DocumentApp.create(docName);

    writeMeetingSections(doc.getBody(), meeting, bills, false);

    return {
      success: true,
      docUrl: doc.getUrl(),
      docName: docName,
      billCount: bills.length
    };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

function appendToDocWithMeeting(docId, meetingUrl) {
  try {
    const meeting = fetchMeetingData(meetingUrl);
    const bills = getBillDetailsForMeeting(meeting.bills);

    const doc = DocumentApp.openById(docId);
    writeMeetingSections(doc.getBody(), meeting, bills, true);

    // FINAL fallback: scrape HTML if APIs failed
    if (!meetingDateTime) {
      try {
        meetingDateTime = scrapeMeetingDateTimeFromHtml(meetingUrl);
      } catch (_) {}
    } 

    return {
      success: true,
      docUrl: doc.getUrl(),
      docName: doc.getName(),
      billCount: bills.length
    };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

/* ===========================
   TRACKER MATCHING
   Matching bills to tracker data in sheet by Legislation ID
=========================== */

function getBillDetailsForMeeting(meetingBills) {
  const sheet = SpreadsheetApp.getActiveSheet();
  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  const idCol = headers.indexOf('Legislation ID');
  const briefingCol = headers.indexOf('Briefing Text');
  const goodBadCol = headers.indexOf('Good/Bad');

  if ([idCol, briefingCol, goodBadCol].includes(-1)) {
    throw new Error('Missing required columns for meeting export.');
  }

  return meetingBills.map(b => {
    for (let i = 1; i < data.length; i++) {
      if (data[i][idCol] == b.legislationId) {
        return {
          ...b,
          briefing: data[i][briefingCol] || '',
          goodBad: data[i][goodBadCol] || '',
          tracked: true
        };
      }
    }
    return { ...b, briefing: '', goodBad: '', tracked: false };
  });
}

/* ===========================
   DOC WRITING (MEETING)
   Write bills info to Doc body
=========================== */

function writeMeetingSections(body, meeting, bills, isAppending) {
  if (isAppending && body.getText().trim()) {
    body.appendParagraph('\n' + '='.repeat(80));
  }

  const title = body.appendParagraph(meeting.committeeName);
  title.setHeading(DocumentApp.ParagraphHeading.HEADING1);

  if (meeting.meetingDateTime) {
    const p = body.appendParagraph(meeting.meetingDateTime);
    p.setLinkUrl(meeting.meetingUrl);
    p.setForegroundColor('#1155cc');
    p.setUnderline(true);
  }

  body.appendParagraph('');

  bills.forEach(b => {
    const color = COLORS[b.goodBad] || null;

    const h = body.appendParagraph(`${b.displayCode} (${b.sponsor})`);
    h.setHeading(DocumentApp.ParagraphHeading.HEADING3);
    if (color) h.setBackgroundColor(color);

    h.editAsText()
      .setLinkUrl(0, b.displayCode.length - 1, b.billUrl);

    if (b.tracked) {
      if (b.briefing && b.briefing.trim()) {
        const p = body.appendParagraph(b.briefing);
        if (color) p.setBackgroundColor(color);
      } else {
        const p = body.appendParagraph('No briefing available');
        p.setItalic(true);
      }
    } else {
      const p = body.appendParagraph('(Not tracked in bill tracker)');
      p.setItalic(true);
    }

    body.appendParagraph('');
  });
}
