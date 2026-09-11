/**
 * HouseholdOS: publish the church spreadsheet into two Google Calendars.
 *
 * Source of truth:
 *   - 26H2-Calendar-Public -> S&L - 26H2 Calendar - Public
 *   - 26H2-Calendar-Helpers -> S&L - 26H2 Calendar - Helpers
 *
 * Normal synchronization does not send invitations or delete events. A separate
 * manually run function can invite only rows explicitly marked 待邀請.
 */

const HOUSEHOLDOS = Object.freeze({
  spreadsheetId: 'PASTE_SPREADSHEET_ID',
  headerRow: 3,
  timezone: 'America/Los_Angeles',
  syncableStatuses: ['已確認', '已发布', '已發佈', '確認'],
  cancelledStatuses: ['已取消', '取消'],
  markerPrefix: 'HouseholdOS Event ID:',
});

/**
 * ONE-TIME SETUP
 *
 * 1. Replace the two PASTE_... values with the Calendar IDs from
 *    Calendar > Settings and sharing > Integrate calendar.
 * 2. Run this function once.
 * 3. Do not use calendar display names here; use their Calendar IDs.
 */
function saveHouseholdOSConfiguration() {
  PropertiesService.getScriptProperties().setProperties({
    SPREADSHEET_ID: HOUSEHOLDOS.spreadsheetId,
    PUBLIC_CALENDAR_ID: 'PASTE_PUBLIC_CALENDAR_ID',
    OPS_CALENDAR_ID: 'PASTE_HELPERS_CALENDAR_ID',
  });
}

/** ONE-TIME SETUP: create the secret used by the HouseholdOS web app adapter. */
function createHouseholdOSWebAppSecret() {
  const secret = Utilities.getUuid() + Utilities.getUuid();
  PropertiesService.getScriptProperties().setProperty('WEB_APP_SHARED_SECRET', secret);
  console.log(`Copy this value to GOOGLE_APPS_SCRIPT_SHARED_SECRET: ${secret}`);
}

/** Main entry point. Run manually first, then install a time trigger. */
function syncChurchCalendars() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    const properties = PropertiesService.getScriptProperties().getProperties();
    const spreadsheetId = requireSetting_(properties, 'SPREADSHEET_ID');
    const publicCalendar = getCalendar_(
      requireSetting_(properties, 'PUBLIC_CALENDAR_ID'),
      'S&L - 26H2 Calendar - Public'
    );
    const opsCalendar = getCalendar_(
      requireSetting_(properties, 'OPS_CALENDAR_ID'),
      'S&L - 26H2 Calendar - Helpers'
    );

    const spreadsheet = SpreadsheetApp.openById(spreadsheetId);

    const publicResult = syncSheet_(spreadsheet, publicCalendar, {
      sheetName: '26H2-Calendar-Public',
      eventIdHeader: 'Public Calendar Event ID',
      titleHeader: '小組安排',
      statusHeader: '活動狀態',
      syncStatusHeader: '同步狀態',
      lastSyncHeader: '最後同步時間',
      buildDescription: buildPublicDescription_,
    });

    syncSheet_(spreadsheet, opsCalendar, {
      sheetName: '26H2-Calendar-Helpers',
      eventIdHeader: '安排 Calendar Event ID',
      titleHeader: '小組安排',
      statusHeader: '活動狀態',
      syncStatusHeader: '同步狀態',
      lastSyncHeader: '最後同步時間',
      buildDescription: buildOpsDescription_,
    });

    copyPublicEventIdsToOps_(spreadsheet, publicResult.eventIdsBySourceId);
  } finally {
    lock.releaseLock();
  }
}

/** Install one hourly reconciliation trigger. Safe to run more than once. */
function installHourlySyncTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === 'syncChurchCalendars')
    .forEach(trigger => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger('syncChurchCalendars')
    .timeBased()
    .everyHours(1)
    .create();
}

/** Install an edit trigger so administrator spreadsheet edits sync automatically. */
function installSpreadsheetEditTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === 'handleHouseholdOSEdit')
    .forEach(trigger => ScriptApp.deleteTrigger(trigger));

  const spreadsheetId = requireSetting_(
    PropertiesService.getScriptProperties().getProperties(), 'SPREADSHEET_ID'
  );
  ScriptApp.newTrigger('handleHouseholdOSEdit')
    .forSpreadsheet(spreadsheetId)
    .onEdit()
    .create();
}

/** Trigger target. Only relevant data-row edits start a reconciliation. */
function handleHouseholdOSEdit(event) {
  if (!event || !event.range) return;
  const sheet = event.range.getSheet();
  if (!['26H2-Calendar-Public', '26H2-Calendar-Helpers'].includes(sheet.getName())) return;
  if (event.range.getRow() <= HOUSEHOLDOS.headerRow) return;
  syncChurchCalendars();
}

/**
 * Deployed web-app endpoint used after a HouseholdOS approval. It updates only
 * allow-listed fields on the matching spreadsheet row, then reconciles calendars.
 */
function doPost(event) {
  try {
    const request = JSON.parse((event && event.postData && event.postData.contents) || '{}');
    const properties = PropertiesService.getScriptProperties().getProperties();
    const expectedSecret = requireSetting_(properties, 'WEB_APP_SHARED_SECRET');
    if (!request.secret || request.secret !== expectedSecret) {
      return jsonResponse_({ ok: false, message: 'Unauthorized' });
    }
    const allowedSheets = ['26H2-Calendar-Public', '26H2-Calendar-Helpers'];
    if (request.action === 'list_events') {
      if (!allowedSheets.includes(request.sheet)) throw new Error('Invalid sheet');
      return jsonResponse_({
        ok: true,
        message: 'Events loaded',
        events: listEventOptions_(properties, request.sheet),
      });
    }
    if (request.action === 'create_event_and_sync') {
      const targetSheets = Array.isArray(request.sheets) ? request.sheets : [];
      if (!targetSheets.length || targetSheets.some(name => !allowedSheets.includes(name))) {
        throw new Error('At least one valid target sheet is required');
      }
      const eventId = String(request.event_id || '').trim();
      if (!eventId) throw new Error('Event ID is required');
      createEventRows_(
        properties, [...new Set(targetSheets)], eventId,
        request.changes || {}, request.sheet_changes || {}
      );
      syncChurchCalendars();
      return jsonResponse_({
        ok: true,
        message: `${eventId} created in ${targetSheets.join(', ')} and calendars synchronized`,
      });
    }
    if (request.action === 'cancel_event_and_sync') {
      const eventId = String(request.event_id || '').trim();
      if (!eventId) throw new Error('Event ID is required');
      const targetSheets = Array.isArray(request.sheets) && request.sheets.length
        ? request.sheets : allowedSheets;
      if (targetSheets.some(name => !allowedSheets.includes(name))) {
        throw new Error('Invalid target sheet');
      }
      const count = cancelEventRows_(properties, [...new Set(targetSheets)], eventId);
      syncChurchCalendars();
      return jsonResponse_({
        ok: true,
        message: `${eventId} cancelled in ${count} spreadsheet row(s) and calendars synchronized`,
      });
    }
    if (request.action === 'coordinate_helpers_and_sync') {
      const eventId = String(request.event_id || '').trim();
      if (!eventId) throw new Error('Event ID is required');
      updateEventRow_(
        properties, '26H2-Calendar-Helpers', eventId, request.changes || {}
      );
      syncChurchCalendars();
      const invitationDetail = request.send_invitations
        ? inviteHelpersForEvent_(properties, eventId)
        : 'Invitations not requested';
      return jsonResponse_({
        ok: true,
        message: `${eventId} helper assignments synchronized. ${invitationDetail}`,
      });
    }
    if (request.action !== 'update_event_and_sync') {
      return jsonResponse_({ ok: false, message: 'Unsupported action' });
    }
    if (!allowedSheets.includes(request.sheet)) throw new Error('Invalid sheet');
    const eventId = String(request.event_id || '').trim();
    if (!eventId) throw new Error('Event ID is required');
    const changes = request.changes || {};
    const allowedFields = editableEventFields_();
    const fields = Object.keys(changes);
    if (!fields.length) throw new Error('At least one change is required');
    fields.forEach(field => {
      if (!allowedFields.has(field)) throw new Error(`Field is not editable: ${field}`);
    });

    const spreadsheet = SpreadsheetApp.openById(requireSetting_(properties, 'SPREADSHEET_ID'));
    const sheet = spreadsheet.getSheetByName(request.sheet);
    const values = sheet.getRange(
      HOUSEHOLDOS.headerRow, 1,
      sheet.getLastRow() - HOUSEHOLDOS.headerRow + 1,
      sheet.getLastColumn()
    ).getDisplayValues();
    const columns = indexHeaders_(values[0]);
    validateHeaders_(columns, ['Event ID', ...fields], request.sheet);
    const offset = values.slice(1).findIndex(row => cell_(row, columns, 'Event ID') === eventId);
    if (offset < 0) throw new Error(`Event ID not found: ${eventId}`);
    const rowNumber = HOUSEHOLDOS.headerRow + 1 + offset;
    fields.forEach(field => setCell_(sheet, rowNumber, columns, field, changes[field]));
    syncChurchCalendars();
    return jsonResponse_({ ok: true, message: `${eventId} updated and calendars synchronized` });
  } catch (error) {
    return jsonResponse_({
      ok: false,
      message: String(error && error.message ? error.message : error).slice(0, 500),
    });
  }
}

/**
 * CONTROLLED WRITE: invite assigned helpers only for rows explicitly marked
 * 來賓邀請狀態 = 待邀請.
 *
 * This function is intentionally NOT called by syncChurchCalendars and is NOT
 * installed as a trigger. Run it manually after reviewing the pending rows.
 */
function sendPendingHelperInvitations() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    const properties = PropertiesService.getScriptProperties().getProperties();
    const spreadsheet = SpreadsheetApp.openById(
      requireSetting_(properties, 'SPREADSHEET_ID')
    );
    const calendar = getCalendar_(
      requireSetting_(properties, 'OPS_CALENDAR_ID'),
      'S&L - 26H2 Calendar - Helpers'
    );
    const sheet = spreadsheet.getSheetByName('26H2-Calendar-Helpers');
    if (!sheet) throw new Error('Missing sheet: 26H2-Calendar-Helpers');

    const lastRow = sheet.getLastRow();
    const lastColumn = sheet.getLastColumn();
    if (lastRow <= HOUSEHOLDOS.headerRow) return;

    const values = sheet
      .getRange(HOUSEHOLDOS.headerRow, 1,
        lastRow - HOUSEHOLDOS.headerRow + 1, lastColumn)
      .getDisplayValues();
    const columns = indexHeaders_(values[0]);
    const invitationHeader = '來賓邀請狀態';
    const calendarEventHeader = '安排 Calendar Event ID';
    const rolePairs = [
      ['查經帶領', '帶領者 Email'],
      ['協助1', '協助1 Email'],
      ['協助2', '協助2 Email'],
    ];
    validateHeaders_(columns, [
      'Event ID', '活動狀態', calendarEventHeader, invitationHeader,
      ...rolePairs.flat(),
    ], sheet.getName());

    values.slice(1).forEach((row, offset) => {
      const sheetRow = HOUSEHOLDOS.headerRow + 1 + offset;
      if (cell_(row, columns, invitationHeader) !== '待邀請') return;

      const sourceId = cell_(row, columns, 'Event ID') || `row ${sheetRow}`;
      const invitationCell = sheet.getRange(sheetRow, columns[invitationHeader] + 1);

      try {
        const activityStatus = cell_(row, columns, '活動狀態');
        if (!isSyncable_(activityStatus)) {
          throw new Error(`${sourceId}: 活動狀態 must be 已確認 before inviting guests`);
        }

        const missingEmailRoles = rolePairs
          .filter(([nameHeader, emailHeader]) =>
            cell_(row, columns, nameHeader) && !cell_(row, columns, emailHeader))
          .map(([nameHeader]) => nameHeader);
        if (missingEmailRoles.length) {
          invitationCell
            .setValue('待補Email')
            .setNote(`缺少 Email：${missingEmailRoles.join('、')}`);
          return;
        }

        const desiredEmails = [...new Set(rolePairs
          .map(([, emailHeader]) => normalizeEmail_(cell_(row, columns, emailHeader)))
          .filter(Boolean))];
        if (!desiredEmails.length) {
          throw new Error(`${sourceId}: no assigned helper emails`);
        }

        const invalidEmails = desiredEmails.filter(email => !isValidEmail_(email));
        if (invalidEmails.length) {
          throw new Error(`${sourceId}: invalid email: ${invalidEmails.join(', ')}`);
        }

        const eventId = cell_(row, columns, calendarEventHeader);
        if (!eventId) {
          throw new Error(`${sourceId}: run syncChurchCalendars first`);
        }
        const event = calendar.getEventById(eventId);
        if (!event) throw new Error(`${sourceId}: Helpers calendar event not found`);

        const marker = `${HOUSEHOLDOS.markerPrefix} ${sourceId}`;
        if (!(event.getDescription() || '').includes(marker)) {
          throw new Error(`${sourceId}: event ID does not match its HouseholdOS marker`);
        }

        const existingEmails = new Set(
          event.getGuestList().map(guest => normalizeEmail_(guest.getEmail()))
        );
        const newlyInvited = [];
        desiredEmails.forEach(email => {
          if (!existingEmails.has(email)) {
            event.addGuest(email);
            newlyInvited.push(email);
          }
        });
        event.setGuestsCanInviteOthers(false);
        event.setGuestsCanModify(false);

        const detail = newlyInvited.length
          ? `新邀請：${newlyInvited.join(', ')}`
          : '所有指派同工已在來賓名單中';
        invitationCell
          .setValue('已邀請')
          .setNote(`${detail}\n${Utilities.formatDate(new Date(), HOUSEHOLDOS.timezone,
            'yyyy-MM-dd HH:mm:ss')}`);
      } catch (error) {
        const message = String(error && error.message ? error.message : error)
          .slice(0, 300);
        invitationCell
          .setValue('邀請錯誤')
          .setNote(`邀請未完成：${message}`);
        console.error(message);
      }
    });
  } finally {
    lock.releaseLock();
  }
}

/** Optional menu when this code is used as a sheet-bound script. */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('HouseholdOS')
    .addItem('同步兩個日曆', 'syncChurchCalendars')
    .addItem('發送待邀請同工', 'sendPendingHelperInvitations')
    .addItem('安裝每小時同步', 'installHourlySyncTrigger')
    .addItem('安裝編輯後自動同步', 'installSpreadsheetEditTrigger')
    .addToUi();
}

function jsonResponse_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function listEventOptions_(properties, sheetName) {
  const spreadsheet = SpreadsheetApp.openById(requireSetting_(properties, 'SPREADSHEET_ID'));
  const sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet || sheet.getLastRow() <= HOUSEHOLDOS.headerRow) return [];
  const values = sheet.getRange(
    HOUSEHOLDOS.headerRow, 1,
    sheet.getLastRow() - HOUSEHOLDOS.headerRow + 1,
    sheet.getLastColumn()
  ).getDisplayValues();
  const columns = indexHeaders_(values[0]);
  validateHeaders_(columns, ['Event ID', '日期', '小組安排', '活動狀態'], sheetName);
  return values.slice(1)
    .map(row => ({
      event_id: cell_(row, columns, 'Event ID'),
      date: cell_(row, columns, '日期'),
      title: cell_(row, columns, '小組安排') || cell_(row, columns, '教會查經安排'),
      bible_passage: cell_(row, columns, '教會查經安排'),
      meeting_mode: cellOffset_(row, columns, '小組安排', 1),
      status: cell_(row, columns, '活動狀態'),
      start_time: cell_(row, columns, '開始時間'),
      end_time: cell_(row, columns, '結束時間'),
      location: cell_(row, columns, '地點'),
      activity_type: cell_(row, columns, '活動類型'),
      leader: cell_(row, columns, '查經帶領'),
      helper_one: cell_(row, columns, '協助1'),
      helper_two: cell_(row, columns, '協助2'),
      leader_email: cell_(row, columns, '帶領者 Email'),
      helper_one_email: cell_(row, columns, '協助1 Email'),
      helper_two_email: cell_(row, columns, '協助2 Email'),
      leader_confirmation: cell_(row, columns, '帶領確認'),
      helper_one_confirmation: cell_(row, columns, '協助1確認'),
      helper_two_confirmation: cell_(row, columns, '協助2確認'),
      preparation_reminder: cell_(row, columns, '預備提醒時間（提前1.5週）'),
      zoom_link: cell_(row, columns, 'Zoom連結'),
      internal_notes: cell_(row, columns, '內部備註'),
      invitation_status: cell_(row, columns, '來賓邀請狀態'),
    }))
    .filter(item => item.event_id);
}

function createEventRows_(properties, sheetNames, eventId, commonChanges, sheetChanges) {
  const commonFields = Object.keys(commonChanges);
  const allowedFields = editableEventFields_();
  if (!commonFields.length) throw new Error('Event details are required');
  const allFields = new Set(commonFields);
  Object.values(sheetChanges).forEach(changes => {
    Object.keys(changes || {}).forEach(field => allFields.add(field));
  });
  [...allFields].forEach(field => {
    if (!allowedFields.has(field)) throw new Error(`Field is not editable: ${field}`);
  });

  const spreadsheet = SpreadsheetApp.openById(requireSetting_(properties, 'SPREADSHEET_ID'));
  const prepared = sheetNames.map(sheetName => {
    const sheet = spreadsheet.getSheetByName(sheetName);
    if (!sheet) throw new Error(`Missing sheet: ${sheetName}`);
    const lastRow = sheet.getLastRow();
    const values = sheet.getRange(
      HOUSEHOLDOS.headerRow, 1,
      Math.max(1, lastRow - HOUSEHOLDOS.headerRow + 1),
      sheet.getLastColumn()
    ).getDisplayValues();
    const columns = indexHeaders_(values[0]);
    const changes = Object.assign({}, commonChanges, sheetChanges[sheetName] || {});
    validateHeaders_(columns, ['Event ID', ...Object.keys(changes)], sheetName);
    if (values.slice(1).some(row => cell_(row, columns, 'Event ID') === eventId)) {
      throw new Error(`${sheetName}: duplicate Event ID ${eventId}`);
    }
    return { sheet, columns, lastRow, changes };
  });

  prepared.forEach(({ sheet, columns, lastRow, changes }) => {
    const rowNumber = Math.max(lastRow + 1, HOUSEHOLDOS.headerRow + 1);
    if (rowNumber > sheet.getMaxRows()) sheet.insertRowAfter(sheet.getMaxRows());
    if (lastRow > HOUSEHOLDOS.headerRow) {
      const template = sheet.getRange(lastRow, 1, 1, sheet.getLastColumn());
      const destination = sheet.getRange(rowNumber, 1, 1, sheet.getLastColumn());
      template.copyTo(destination, SpreadsheetApp.CopyPasteType.PASTE_FORMAT, false);
      template.copyTo(destination, SpreadsheetApp.CopyPasteType.PASTE_DATA_VALIDATION, false);
    }
    setCell_(sheet, rowNumber, columns, 'Event ID', eventId);
    Object.keys(changes).forEach(field => setCell_(sheet, rowNumber, columns, field, changes[field]));
  });
}

function cancelEventRows_(properties, sheetNames, eventId) {
  const spreadsheet = SpreadsheetApp.openById(requireSetting_(properties, 'SPREADSHEET_ID'));
  let updated = 0;
  sheetNames.forEach(sheetName => {
    const sheet = spreadsheet.getSheetByName(sheetName);
    if (!sheet || sheet.getLastRow() <= HOUSEHOLDOS.headerRow) return;
    const values = sheet.getRange(
      HOUSEHOLDOS.headerRow, 1,
      sheet.getLastRow() - HOUSEHOLDOS.headerRow + 1,
      sheet.getLastColumn()
    ).getDisplayValues();
    const columns = indexHeaders_(values[0]);
    validateHeaders_(columns, ['Event ID', '活動狀態'], sheetName);
    const offset = values.slice(1).findIndex(row => cell_(row, columns, 'Event ID') === eventId);
    if (offset >= 0) {
      setCell_(sheet, HOUSEHOLDOS.headerRow + 1 + offset, columns, '活動狀態', '已取消');
      updated += 1;
    }
  });
  if (!updated) throw new Error(`Event ID not found: ${eventId}`);
  return updated;
}

function updateEventRow_(properties, sheetName, eventId, changes) {
  const fields = Object.keys(changes);
  if (!fields.length) throw new Error('At least one helper change is required');
  const allowedFields = editableEventFields_();
  fields.forEach(field => {
    if (!allowedFields.has(field)) throw new Error(`Field is not editable: ${field}`);
  });
  const spreadsheet = SpreadsheetApp.openById(requireSetting_(properties, 'SPREADSHEET_ID'));
  const sheet = spreadsheet.getSheetByName(sheetName);
  const values = sheet.getRange(
    HOUSEHOLDOS.headerRow, 1,
    sheet.getLastRow() - HOUSEHOLDOS.headerRow + 1,
    sheet.getLastColumn()
  ).getDisplayValues();
  const columns = indexHeaders_(values[0]);
  validateHeaders_(columns, ['Event ID', ...fields], sheetName);
  const offset = values.slice(1).findIndex(row => cell_(row, columns, 'Event ID') === eventId);
  if (offset < 0) throw new Error(`Event ID not found: ${eventId}`);
  const rowNumber = HOUSEHOLDOS.headerRow + 1 + offset;
  fields.forEach(field => setCell_(sheet, rowNumber, columns, field, changes[field]));
}

function inviteHelpersForEvent_(properties, eventId) {
  const spreadsheet = SpreadsheetApp.openById(requireSetting_(properties, 'SPREADSHEET_ID'));
  const calendar = getCalendar_(
    requireSetting_(properties, 'OPS_CALENDAR_ID'), 'S&L - 26H2 Calendar - Helpers'
  );
  const sheet = spreadsheet.getSheetByName('26H2-Calendar-Helpers');
  const values = sheet.getRange(
    HOUSEHOLDOS.headerRow, 1,
    sheet.getLastRow() - HOUSEHOLDOS.headerRow + 1,
    sheet.getLastColumn()
  ).getDisplayValues();
  const columns = indexHeaders_(values[0]);
  const rolePairs = [
    ['查經帶領', '帶領者 Email'], ['協助1', '協助1 Email'], ['協助2', '協助2 Email']
  ];
  validateHeaders_(columns, [
    'Event ID', '活動狀態', '安排 Calendar Event ID', '來賓邀請狀態',
    ...rolePairs.flat()
  ], sheet.getName());
  const offset = values.slice(1).findIndex(row => cell_(row, columns, 'Event ID') === eventId);
  if (offset < 0) throw new Error(`Event ID not found: ${eventId}`);
  const row = values[offset + 1];
  if (!isSyncable_(cell_(row, columns, '活動狀態'))) {
    throw new Error(`${eventId}: 活動狀態 must be 已確認 before inviting helpers`);
  }
  const missingEmailRoles = rolePairs
    .filter(([nameHeader, emailHeader]) =>
      cell_(row, columns, nameHeader) && !cell_(row, columns, emailHeader))
    .map(([nameHeader]) => nameHeader);
  if (missingEmailRoles.length) throw new Error(`Missing Email: ${missingEmailRoles.join(', ')}`);
  const desiredEmails = [...new Set(rolePairs
    .map(([, emailHeader]) => normalizeEmail_(cell_(row, columns, emailHeader)))
    .filter(Boolean))];
  if (!desiredEmails.length) throw new Error(`${eventId}: no assigned helper emails`);
  const invalidEmails = desiredEmails.filter(email => !isValidEmail_(email));
  if (invalidEmails.length) throw new Error(`Invalid email: ${invalidEmails.join(', ')}`);
  const calendarEventId = cell_(row, columns, '安排 Calendar Event ID');
  const event = calendarEventId ? calendar.getEventById(calendarEventId) : null;
  if (!event) throw new Error(`${eventId}: Helpers calendar event not found`);
  if (!(event.getDescription() || '').includes(`${HOUSEHOLDOS.markerPrefix} ${eventId}`)) {
    throw new Error(`${eventId}: calendar marker mismatch`);
  }
  const existingEmails = new Set(event.getGuestList().map(guest => normalizeEmail_(guest.getEmail())));
  const newlyInvited = [];
  desiredEmails.forEach(email => {
    if (!existingEmails.has(email)) {
      event.addGuest(email);
      newlyInvited.push(email);
    }
  });
  event.setGuestsCanInviteOthers(false);
  event.setGuestsCanModify(false);
  const rowNumber = HOUSEHOLDOS.headerRow + 1 + offset;
  sheet.getRange(rowNumber, columns['來賓邀請狀態'] + 1)
    .setValue('已邀請')
    .setNote(`HouseholdOS invitation execution: ${Utilities.formatDate(
      new Date(), HOUSEHOLDOS.timezone, 'yyyy-MM-dd HH:mm:ss'
    )}`);
  return newlyInvited.length
    ? `Invited ${newlyInvited.length} newly assigned helper(s)`
    : 'All assigned helpers were already guests';
}

function editableEventFields_() {
  return new Set([
    '日期', '小組安排', '教會查經安排', '開始時間', '結束時間', '地點',
    'Zoom連結', '活動狀態', '建議抵達時間', '活動類型', '同工',
    '查經帶領', '協助1', '協助2', '帶領者 Email', '協助1 Email',
    '協助2 Email', '帶領確認', '協助1確認', '協助2確認',
    '預備提醒時間（提前1.5週）', '內部備註', '來賓邀請狀態'
  ]);
}

function syncSheet_(spreadsheet, calendar, config) {
  const sheet = spreadsheet.getSheetByName(config.sheetName);
  if (!sheet) throw new Error(`Missing sheet: ${config.sheetName}`);

  const lastRow = sheet.getLastRow();
  const lastColumn = sheet.getLastColumn();
  if (lastRow <= HOUSEHOLDOS.headerRow) return { eventIdsBySourceId: {} };

  // Display values make dates and AM/PM times deterministic across Sheets formats.
  const values = sheet
    .getRange(HOUSEHOLDOS.headerRow, 1, lastRow - HOUSEHOLDOS.headerRow + 1, lastColumn)
    .getDisplayValues();
  const headers = values[0];
  const columns = indexHeaders_(headers);
  validateHeaders_(columns, [
    'Event ID', '日期', config.titleHeader, config.statusHeader,
    config.eventIdHeader, config.syncStatusHeader, config.lastSyncHeader,
  ], config.sheetName);

  const eventIdsBySourceId = {};

  values.slice(1).forEach((row, offset) => {
    const sheetRow = HOUSEHOLDOS.headerRow + 1 + offset;
    const sourceId = cell_(row, columns, 'Event ID');
    if (!sourceId) return;

    const storedEventId = cell_(row, columns, config.eventIdHeader);
    const status = cell_(row, columns, config.statusHeader);

    try {
      if (!isSyncable_(status) && !isCancelled_(status)) {
        const detail = storedEventId ? '草稿（保留現有日曆）' : '草稿未同步';
        setSyncStatus_(sheet, sheetRow, columns, config.syncStatusHeader,
          '未同步', detail);
        if (storedEventId) eventIdsBySourceId[sourceId] = storedEventId;
        return;
      }

      const eventData = buildEventData_(row, columns, config, sourceId);
      let event = storedEventId ? calendar.getEventById(storedEventId) : null;
      if (!event) event = recoverEventByMarker_(calendar, eventData);

      if (isCancelled_(status) && !event) {
        setSyncStatus_(sheet, sheetRow, columns, config.syncStatusHeader,
          '已同步', '已取消：目標日曆中沒有事件');
        setCell_(sheet, sheetRow, columns, config.lastSyncHeader, new Date());
        return;
      }

      event = upsertEvent_(calendar, event, eventData);
      if (isCancelled_(status)) markCancelled_(event, eventData);

      const eventId = event.getId();
      setCell_(sheet, sheetRow, columns, config.eventIdHeader, eventId);
      setSyncStatus_(sheet, sheetRow, columns, config.syncStatusHeader,
        '已同步', isCancelled_(status) ? '日曆事件已標記取消' : '');
      setCell_(sheet, sheetRow, columns, config.lastSyncHeader, new Date());
      eventIdsBySourceId[sourceId] = eventId;
    } catch (error) {
      const message = String(error && error.message ? error.message : error).slice(0, 180);
      setSyncStatus_(sheet, sheetRow, columns, config.syncStatusHeader,
        '同步錯誤', message);
    }
  });

  return { eventIdsBySourceId };
}

function buildEventData_(row, columns, config, sourceId) {
  const dateText = cell_(row, columns, '日期');
  const title = cell_(row, columns, config.titleHeader) || cell_(row, columns, '教會查經安排');
  if (!dateText) throw new Error(`${sourceId}: missing 日期`);
  if (!title) throw new Error(`${sourceId}: missing event title`);

  const date = parseDate_(dateText);
  const startText = cell_(row, columns, '開始時間');
  const endText = cell_(row, columns, '結束時間');
  const allDay = !startText;
  const start = allDay ? date : combineDateTime_(date, startText);
  const end = allDay ? null : combineDateTime_(date, endText || '9:00 PM');
  if (end && end <= start) end.setDate(end.getDate() + 1);

  const marker = `${HOUSEHOLDOS.markerPrefix} ${sourceId}`;
  const descriptionBody = config.buildDescription(row, columns);
  return {
    sourceId,
    title,
    description: [descriptionBody, marker].filter(Boolean).join('\n\n'),
    location: cell_(row, columns, '地點'),
    allDay,
    start,
    end,
  };
}

function upsertEvent_(calendar, event, data) {
  if (!event) {
    const options = { description: data.description, location: data.location };
    return data.allDay
      ? calendar.createAllDayEvent(data.title, data.start, options)
      : calendar.createEvent(data.title, data.start, data.end, options);
  }

  event.setTitle(data.title);
  event.setDescription(data.description);
  event.setLocation(data.location || '');
  if (data.allDay) event.setAllDayDate(data.start);
  else event.setTime(data.start, data.end);
  return event;
}

function recoverEventByMarker_(calendar, data) {
  const windowStart = new Date(data.start);
  const windowEnd = new Date(data.end || data.start);
  windowStart.setDate(windowStart.getDate() - 2);
  windowEnd.setDate(windowEnd.getDate() + 3);
  const marker = `${HOUSEHOLDOS.markerPrefix} ${data.sourceId}`;
  return calendar.getEvents(windowStart, windowEnd)
    .find(event => (event.getDescription() || '').includes(marker)) || null;
}

function markCancelled_(event, data) {
  if (!event.getTitle().startsWith('[已取消]')) {
    event.setTitle(`[已取消] ${data.title}`);
  }
  try {
    event.setColor(CalendarApp.EventColor.GRAY);
  } catch (ignored) {
    // Event color availability can differ across Calendar account types.
  }
}

function buildPublicDescription_(row, columns) {
  return joinFields_([
    ['教會安排', cell_(row, columns, '教會查經安排')],
    ['小組安排', cell_(row, columns, '小組安排')],
    // The current sheet's meeting-mode column (online/offline) has no header
    // and sits immediately after 小組安排.
    ['聚會方式', cellOffset_(row, columns, '小組安排', 1)],
    ['建議抵達時間', cell_(row, columns, '建議抵達時間')],
    ['Zoom', cell_(row, columns, 'Zoom連結')],
  ]);
}

function buildOpsDescription_(row, columns) {
  return joinFields_([
    ['教會安排', cell_(row, columns, '教會查經安排')],
    ['小組安排', cell_(row, columns, '小組安排')],
    ['聚會方式', cellOffset_(row, columns, '小組安排', 1)],
    ['同工', cell_(row, columns, '同工')],
    ['活動類型', cell_(row, columns, '活動類型')],
    ['查經帶領', cell_(row, columns, '查經帶領')],
    ['協助1', cell_(row, columns, '協助1')],
    ['協助2', cell_(row, columns, '協助2')],
    ['帶領確認', cell_(row, columns, '帶領確認')],
    ['協助1確認', cell_(row, columns, '協助1確認')],
    ['協助2確認', cell_(row, columns, '協助2確認')],
    ['預備提醒時間', cell_(row, columns, '預備提醒時間（提前1.5週）')],
    ['建議抵達時間', cell_(row, columns, '建議抵達時間')],
    ['Zoom', cell_(row, columns, 'Zoom連結')],
    ['內部備註', cell_(row, columns, '內部備註')],
  ]);
}

function copyPublicEventIdsToOps_(spreadsheet, eventIdsBySourceId) {
  const sheet = spreadsheet.getSheetByName('26H2-Calendar-Helpers');
  if (!sheet || sheet.getLastRow() <= HOUSEHOLDOS.headerRow) return;
  const range = sheet.getRange(
    HOUSEHOLDOS.headerRow,
    1,
    sheet.getLastRow() - HOUSEHOLDOS.headerRow + 1,
    sheet.getLastColumn()
  );
  const values = range.getDisplayValues();
  const columns = indexHeaders_(values[0]);
  validateHeaders_(columns, ['Event ID', 'Public Calendar Event ID'], sheet.getName());

  values.slice(1).forEach((row, offset) => {
    const sourceId = cell_(row, columns, 'Event ID');
    const publicEventId = eventIdsBySourceId[sourceId];
    if (publicEventId) {
      setCell_(sheet, HOUSEHOLDOS.headerRow + 1 + offset, columns,
        'Public Calendar Event ID', publicEventId);
    }
  });
}

function parseDate_(text) {
  const match = String(text).trim().match(/^(\d{1,4})[\/-](\d{1,2})[\/-](\d{1,4})$/);
  if (!match) throw new Error(`invalid date: ${text}`);
  let year;
  let month;
  let day;
  if (match[1].length === 4) {
    year = Number(match[1]); month = Number(match[2]); day = Number(match[3]);
  } else {
    month = Number(match[1]); day = Number(match[2]); year = Number(match[3]);
  }
  if (year < 100) year += 2000;
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    throw new Error(`invalid date: ${text}`);
  }
  return date;
}

function combineDateTime_(date, text) {
  const normalized = String(text).trim()
    .replace('上午', 'AM')
    .replace('下午', 'PM');
  const match = normalized.match(/^(\d{1,2}):(\d{2})(?:\s*(AM|PM))?$/i);
  if (!match) throw new Error(`invalid time: ${text}`);
  let hour = Number(match[1]);
  const minute = Number(match[2]);
  const meridiem = (match[3] || '').toUpperCase();
  if (meridiem === 'PM' && hour !== 12) hour += 12;
  if (meridiem === 'AM' && hour === 12) hour = 0;
  if (hour > 23 || minute > 59) throw new Error(`invalid time: ${text}`);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), hour, minute, 0, 0);
}

function indexHeaders_(headers) {
  return headers.reduce((result, header, index) => {
    const name = String(header || '').trim();
    if (name) result[name] = index;
    return result;
  }, {});
}

function validateHeaders_(columns, required, sheetName) {
  const missing = required.filter(header => columns[header] === undefined);
  if (missing.length) throw new Error(`${sheetName} missing headers: ${missing.join(', ')}`);
}

function cell_(row, columns, header) {
  if (!header || columns[header] === undefined) return '';
  return String(row[columns[header]] || '').trim();
}

function cellOffset_(row, columns, anchorHeader, offset) {
  if (columns[anchorHeader] === undefined) return '';
  return String(row[columns[anchorHeader] + offset] || '').trim();
}

function setCell_(sheet, rowNumber, columns, header, value) {
  sheet.getRange(rowNumber, columns[header] + 1).setValue(value);
}

function setSyncStatus_(sheet, rowNumber, columns, header, status, detail) {
  sheet.getRange(rowNumber, columns[header] + 1)
    .setValue(status)
    .setNote(detail || '');
}

function joinFields_(fields) {
  return fields
    .filter(([, value]) => value)
    .map(([label, value]) => `${label}：${value}`)
    .join('\n');
}

function isSyncable_(status) {
  return HOUSEHOLDOS.syncableStatuses.includes(String(status).trim());
}

function isCancelled_(status) {
  return HOUSEHOLDOS.cancelledStatuses.includes(String(status).trim());
}

function normalizeEmail_(email) {
  return String(email || '').trim().toLowerCase();
}

function isValidEmail_(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function requireSetting_(properties, key) {
  const value = properties[key];
  if (!value || value.startsWith('PASTE_')) {
    throw new Error(`Run saveHouseholdOSConfiguration after setting ${key}`);
  }
  return value;
}

function getCalendar_(calendarId, expectedName) {
  const calendar = CalendarApp.getCalendarById(calendarId);
  if (!calendar) {
    throw new Error(`Cannot access ${expectedName}. Check its Calendar ID and permissions.`);
  }
  return calendar;
}
