# Property operations suite

The **Operations** section adds maintenance, recurring bills, housekeeping, waitlist, owner access,
operational health, and ERPNext screens. The owner portal is served at `/owners`. Language selection
is available in the manager, tenant, and owner apps.

## Workflows

| Feature | Working flow |
| --- | --- |
| Maintenance | Add a vendor, create and assign a work order, request a quote review, approve with a different manager or assigned owner, start work, attach a completion photo and notes, record actual cost, then record payment. Tenants confirm completed work linked to their maintenance request from **Requests**. |
| Recurring bills | Create weekly, monthly, quarterly, or yearly schedules. Daily generation creates **Due** bills, not paid expenses. Record payment separately; existing expense approval policies apply. Pause schedules or cancel individual unpaid bills with a reason. |
| Owner portal | Assign an existing enabled User to one or more properties. Owners see date-filtered rental cash collections, expenses and net cash, current outstanding balances/occupancy, repairs, pending quote decisions and explicitly shared private documents. Revoke a grant to remove access immediately. |
| Housekeeping | Assign daily, weekly, or monthly schedules with 1–30 checklist items. Daily generation snapshots tasks; assignees complete every item and attach a photo when required. Managers verify or reopen. Overdue tasks appear in the app and create daily staff notification records. |
| Waitlist | Store budget, room type, contact details and intended move-in date. Match current vacancy, issue a tentative offer lasting 1–14 days, withdraw/close, or accept into a Contacted lead. Expired offers return to Waiting. Finish the normal lead booking/move-in process to reserve a bed. |
| Operational health | Inspect wrapped invoice generation, rent reminders, payment reconciliation and suite jobs; recent failed message records; sync failures; overdue cleaning; successful local/offsite backup timestamps. System Managers can queue only whitelisted jobs. |
| Hindi/English | Save a language preference on the signed-in User, restore it across devices, translate new operations screens and shared navigation/labels, and select Hindi tenant message templates for linked tenant users. |
| ERPNext | Configure encrypted API credentials and account mappings, queue source documents, inspect draft creation status and source changes, and retry failures with stable remote idempotency keys. Integration starts disabled. |

Quotes require a second reviewer even when financial expense approvals are disabled. Quote approval
does not record a payment. Recording payment invokes the existing financial approval pipeline. Paid
bill/repair expense amounts, dates, property and payment details cannot subsequently be edited or
deleted through Desk or REST, preventing the source record and financial evidence from diverging.

Schedules retain their original calendar day across short months (31 January → 28 February →
31 March). Each schedule/date pair is unique. Generation locks schedules and rechecks active state;
backlog processing is capped at 24 bills or 31 cleaning tasks per schedule per run. Run generation
again to catch up a larger backlog. Changing the start date requires a new schedule. Other schedule
edits affect future tasks/bills, not previously generated records.

Waitlist offers do **not** send messages or hold beds. Matching is deliberately conservative: booked
leads reduce availability, and an expected departure is not treated as a completed checkout. The
requested move-in date is carried into the lead; future availability must still be verified. Budget
matching uses the current room rent and does not estimate future rent increases.

Owner reports exclude deposit applications from cash collections, and do not include security deposit
collections as rental income. Current occupancy/outstanding balances are not historical snapshots.
Owner accounts must already exist; granting access does not send an invitation or expose tenant PII.
Private photos/documents are downloaded through endpoints that recheck the current grant or assignment.

## Deployment and validation

1. Back up the site, then install the branch on a staging bench.
2. Run `bench --site SITE migrate` to create the 12 new DocTypes and load scheduler changes.
3. Run `bench build --app rent_management` (the app's normal frontend build), then clear website cache
   and restart workers using the deployment's normal process. `npm run build --prefix frontend` also
   builds all six frontend entry points. Generated bundles and `www/owners.html` are intentionally
   ignored in git, like the existing manager and tenant bundles.
4. Ensure the site's scheduler and background workers are enabled. Assign existing cleaning staff the
   new **Housekeeping** work area in their login settings; the Cleaner preset includes it for new grants.
5. On a dedicated test site, run:

   ```sh
   bench --site TEST_SITE run-tests --app rent_management --module rent_management.tests.test_suite
   bench --site TEST_SITE run-tests --app rent_management --module rent_management.tests.test_operations
   bench --site TEST_SITE run-tests --app rent_management --module rent_management.tests.test_notifications
   bench --site TEST_SITE run-tests --app rent_management --module rent_management.tests.test_access
   ```

Local checks (no Frappe database or outbound API):

```sh
python -m unittest discover -s tests/unit -v
cd frontend
node --test tests/suite.test.mjs tests/occupancy.test.js
npm run build
```

The local service tests isolate Frappe dependencies; they do not replace the migrated-site integration
suite. Test the complete manager/staff/owner/tenant flow on staging before deployment. Job history
covers the listed wrappers from installation onward, not all pre-existing Frappe background jobs.
A worker forcibly terminated during execution may leave a Running entry; inspect worker logs before
retrying. Failed message rows link back to invoice review; automatic job retry retains existing daily
reminder deduplication rather than blindly resending all past failures.

Backup timestamps are written only after successful `bench rent-backup-all` backup/copy operations.
Other backup systems are not tracked. These timestamps are not proof that backups can be restored.

## Hindi messages

The preference is the linked tenant User's `language`; tenants without a linked User default to English.
Hindi templates cover rent reminder/due/overdue, receipt, request update, referral, notice and deposit
settlement messages. User-entered names, addresses, notes and notice content are preserved. Older
specialist screens and untranslated server errors fall back to English. Public signup/listing/check-in
pages continue to default to English. The UI dictionary is `frontend/src/locales/hi.json`.

For WhatsApp, approve Hindi templates with the same parameter counts/order as the existing English
ones, then configure `whatsapp_templates_hi` in site configuration. For example:

```json
{
  "whatsapp_templates_hi": {
    "rent_reminder": "rent_reminder_hi",
    "rent_overdue": "rent_overdue_hi",
    "rent_receipt": "rent_receipt_hi",
    "rent_request_update": "rent_request_update_hi",
    "rent_notice": "rent_notice_hi",
    "rent_referral_reward": "rent_referral_reward_hi",
    "rent_deposit_settled": "rent_deposit_settled_hi"
  }
}
```

Missing Hindi template configuration produces a logged WhatsApp failure instead of sending an
unapproved language variant. Email uses the Hindi text independently when email delivery is enabled.
No provider configuration, live message send, or external account creation is part of this source change.

## ERPNext setup and boundaries

Only System Managers configure the connection. Use a dedicated least-privilege ERPNext API account
that can read Company/Account/Item/Customer Group/Territory and the required Custom Fields, and
create/read Customer, Sales Invoice, Payment Entry, and Journal Entry. The hostname must use public
HTTPS without credentials, a path or a custom port. Redirects are refused; requests have timeouts.

Add a **unique Data field named `custom_rent_sync_key`** on each of Customer, Sales Invoice, Payment
Entry and Journal Entry. Enabling the connection verifies these fields and account company/currency.
Map a non-stock rent service item, company, currency, income, expense, deposit liability, receivable,
bank and cash accounts, plus customer group/territory and optional cost center. Source and destination
currencies must match. A site with sync history cannot change the destination/company.

- Submitted rent invoice → draft Sales Invoice using the final amount and configured rent item.
- Submitted rent payment → draft Payment Entry referencing an already **submitted** ERPNext Sales
  Invoice. Cash routes to cash; other receipt modes route to bank.
- Security Deposit payment → draft balanced Journal Entry debiting deposit liability and crediting
  customer receivable against that Sales Invoice; it does not create another cash receipt.
- Property expense → draft balanced Journal Entry debiting expense and crediting cash/bank.
- Collected original allotment deposit → draft bank/deposit-liability Journal Entry. The source does
  not record a collection mode, so verify the bank mapping before submitting the draft.

Customers use the tenant's name; identity documents, phone numbers and other tenant PII are not copied.
Remote documents remain drafts for accounting review. Taxes, deposit refunds/transfers, cancellations,
refund payments, and edits after sync require manual reconciliation. Transferred-in deposits are
blocked to prevent double counting. Review remote taxes/defaults and totals before submitting.

Every queued source stores its modified timestamp. Changes to the source block processing; the old
snapshot is never silently replaced. Source changes after a successful sync are flagged in the UI.
Retry looks up the stable unique key first, so a successful remote POST with a lost response is reused.
Cancelled remote documents are not recreated. Reconcile stale snapshots or cancelled remote documents
manually; use the sync key when investigating. No destructive resync or automatic posting is provided.
