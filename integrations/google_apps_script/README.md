# S&L 26H2 spreadsheet-to-calendar sync

This Google Apps Script publishes the Google Sheet into two derived subscription
calendars. The spreadsheet remains the single source of truth.

## Mapping

| Spreadsheet tab | Google Calendar | Tracking columns |
| --- | --- | --- |
| `26H2-Calendar-Public` | `S&L - 26H2 Calendar - Public` | K-M |
| `26H2-Calendar-Helpers` | `S&L - 26H2 Calendar - Helpers` | U-X |

Only rows whose `活動狀態` is `已確認`, `已發佈`, `已发布`, or `確認` are
created or updated. `草稿` rows stay out of Calendar. `已取消` rows are visibly marked
as cancelled but are not automatically deleted.

The script does not add guests or send invitation emails. Google Group calendar
sharing controls who can see each calendar during normal synchronization. Guest
invitations are available only through a separate, manually run function.

## Install

1. Sign in with the Google account that owns both calendars and can edit the sheet.
2. Open <https://script.google.com/> and create a new project.
3. In **Project Settings**, set the project time zone to `America/Los_Angeles`.
4. Replace the default editor content with `Code.gs` from this directory.
5. In Google Calendar, open each calendar's **Settings and sharing** page. Under
   **Integrate calendar**, copy its Calendar ID.
6. Confirm the Public and Helpers Calendar IDs inside
   `saveHouseholdOSConfiguration`.
7. Run `saveHouseholdOSConfiguration` once (or again after changing an ID).
8. Change one test row, preferably `CH-26H2-003`, from `草稿` to `已確認` in
   both tabs.
9. Run `syncChurchCalendars`. Review the Google authorization request carefully;
   access to the spreadsheet and calendars is expected.
10. Verify the test event in both calendars and verify that coworker assignments
    are absent from the Public event.
11. Change the other approved rows to `已確認`, then run the sync again.
12. Run `installHourlySyncTrigger` once as a fallback reconciliation.
13. Run `installSpreadsheetEditTrigger` once. Edits made by a person in either
    source tab will then start synchronization automatically.

## HouseholdOS approved edits

To let the app update one reviewed spreadsheet field and then synchronize both
calendars:

1. Run `createHouseholdOSWebAppSecret` once. Copy the value from the execution log
   into `GOOGLE_APPS_SCRIPT_SHARED_SECRET` in the app's `.env`; never put it in Git.
2. Choose **Deploy → New deployment → Web app**.
3. Execute as the calendar-owning S&L account. Restrict who can invoke the deployment
   as tightly as your Google account type permits.
4. Copy the deployed `/exec` URL into `GOOGLE_APPS_SCRIPT_WEB_APP_URL`.
5. Restart Streamlit. The Ministry page should show **Calendar adapter: Ready**.
6. In HouseholdOS, identify the tab, stable Event ID, field, and new value. Queue the
   exact change, approve it, and then execute it from **Approvals**.

The endpoint allow-lists editable column names, locates the row by stable `Event ID`,
updates the spreadsheet first, and calls the existing reconciliation. Tracking IDs,
sync status, and last-sync columns cannot be changed through the endpoint.

The endpoint also supports read-only event listing for the HouseholdOS month view,
approval-gated creation in one or both source tabs, and cancellation by stable Event ID.
Creation copies formatting and data validation from the preceding data row before
writing values. Cancellation keeps the source rows and sets `活動狀態` to `已取消`.

## Controlled helper invitations

The hourly synchronization never sends invitations. To invite the assigned people
for selected Helpers events:

1. Confirm the row is already `已確認` and has an `安排 Calendar Event ID`.
2. Verify `帶領者 Email`, `協助1 Email`, and `協助2 Email` against the
   assigned names.
3. Change that row's `來賓邀請狀態` to `待邀請`.
4. Review every pending row, then manually run
   `sendPendingHelperInvitations` in Apps Script.
5. After success, the function changes the row to `已邀請` and stores the
   invited addresses and timestamp in a cell note.

The function adds only the three row-level assignment emails, never a Google Group.
It skips guests already on the event, does not remove former guests, and leaves a
failed row as `邀請錯誤` with an explanatory note. After fixing the issue,
change it back to `待邀請` and rerun the function. If an assigned name lacks an
email, the row changes to `待補Email`. Removing a former guest remains a manual
Calendar action because it can send a cancellation notice.

## Behavior

- A blank Calendar Event ID creates one event and stores the new ID in the hidden
  tracking column.
- The validated `同步狀態` column contains only `未同步`, `已同步`, or
  `同步錯誤`. Additional details are stored in the status cell's note.
- A populated Calendar Event ID updates that event, so normal runs do not create
  duplicates.
- If the stored ID is lost, the script searches nearby events for the embedded
  stable `Event ID` marker before creating a replacement.
- Rows removed from the sheet are not silently deleted from Calendar. Mark a row
  `已取消` instead so the cancellation remains auditable.
- Calendar edits are overwritten on the next sync. Make authoritative changes in
  the spreadsheet.
- Apps Script/API writes do not fire the spreadsheet edit trigger. HouseholdOS uses
  the protected web-app endpoint for that path, while the hourly trigger remains a
  recovery mechanism.

## Permissions

The executing Google account needs edit access to the spreadsheet and permission
to make changes to both target calendars. Members and coworkers do not need access
to the script or its tracking columns.
