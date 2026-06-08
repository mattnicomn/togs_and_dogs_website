# Matthew-to-Ryan Handoff Message

Here is the draft message you can send directly to Ryan to initiate the structured testing phase.

***

Hi Ryan,

The production readiness checks and end-to-end dry runs for the Google Calendar integration card and the Daily Dispatch export sheet are complete and have passed validation successfully on the live production environment.

We are ready for you to begin structured testing to verify everything looks and feels right from your operational perspective. 

I have put together a step-by-step walkthrough and checklist for you here:
`docs/operations/ryan-structured-testing-checklist.md`

### Guidelines for Testing:
1. **Use Test Data First**: Please use ONLY the pre-configured test accounts specified in the checklist (`admin@toganddogs.com`, client `brearockwell@gmail.com`, and staff `mattnicomn10@yahoo.com`).
2. **Do Not Modify Real Customers**: Avoid opening, modifying, or deleting any live client or sitter records.
3. **No Real Customer Emails**: Do not send test bookings to actual customers.
4. **Mark Test Data Clearly**: When creating any new request, prepend `[RYAN TEST]` to the names.

### What is Ready for Testing:
* The Admin Dashboard Google Calendar connection health status banner.
* Public client intake requests and Terms/Privacy acceptance.
* Satisfying Meet & Greet requirements before request approval.
* Sitter assignment and automatic Google Calendar event creation.
* Sitter mobile schedules and completions (with visit notes).
* Downloading the **Daily Sitter Dispatch** sheet as the first tab in the Excel export workbook.
* Archiving test data through the admin controls.

Please record any feedback or issues you observe using the template here:
`docs/operations/ryan-testing-feedback-template.md`

Let me know once you have completed the walkthrough or if you run into any issues.

Thanks,
Matthew
