### Rent Management System

A [Frappe](https://frappe.io) app for PGs, hostels and rented buildings: buildings, rooms and beds,
tenants, monthly rent invoices, online rent collection, reminders, electricity, expenses and profit,
a tenant app, and everything needed to sell it as a hosted subscription service (SaaS).

- [Features](#features)
- [Web app for managers (`/rent`)](#web-app-for-managers-rent)
- [Tenant app (`/tenant`)](#tenant-app-tenant)
- [Collecting rent online](#collecting-rent-online)
- [Reminders and receipts (WhatsApp and email)](#reminders-and-receipts-whatsapp-and-email)
- [Selling it as SaaS](#selling-it-as-saas)
- [Configuration reference](#configuration-reference)
- [Demo data](#demo-data) · [Workflow](#workflow) · [Installation](#installation) · [Contributing](#contributing)

### Features

- **Photos** - every building and tenant can have a photo, shown on building and room cards, in lists and
  in the tenant app. Tenants can set their own from the tenant app. Tenant photos are private files.
- **Buildings (Rent Property)** - one site can run several buildings. Every list, report and the dashboard
  can be filtered by building.
- **Tenant Space Type / Tenant Space** - room types with standard rent and deposit, and rooms with a number
  of **beds**, so a shared room can hold several tenants. A room is Available, Partly Occupied, Reserved,
  Occupied or Under Renovation.
- **Tenant** - contact, personal and professional details. **Aadhaar numbers** are checksum-validated,
  stored encrypted and shown masked (last 4 digits); revealing the full number is logged.
- **Tenant Space Allotment** - gives a tenant a bed in a room. It holds the rental agreement: rent, deposit,
  agreement period, lock-in, notice period and yearly rent increase.
  - **Notice** - record the date the tenant gave notice; the vacate date follows from the notice period.
  - **Rent revisions** - change the rent from a date (a **Rent Revision** is kept for each change), and
    the yearly increase is applied automatically on the agreement anniversary.
  - **Rental agreement** - a printable agreement from your terms, ready to sign.
- **Tenant Rent Invoice** - one per allotment per month, pro-rated for move-in and move-out months, with
  extra charges, discounts, and paid / outstanding tracking (Unpaid, Partly Paid, Paid, Overdue). The
  invoice print has a **UPI QR code** for the exact balance.
- **Rent Payment** - Cash, UPI, Bank Transfer, Cheque... against an invoice. A receipt is sent to the tenant.
- **Electricity (Meter Reading)** - enter the readings of rooms with a meter. The units are split between
  the tenants who stayed since the last reading, by days, and added to their next invoice.
- **Expenses and profit (Property Expense)** - record expenses per building (salaries, repairs,
  electricity bills...) and see profit and loss per building and month (collected rent minus expenses).
- **Requests (Maintenance Request)** - complaints and requests from tenants (or entered by managers), with
  status, priority and updates sent to the tenant.
- **Security Deposit Settlement** - deductions, using the deposit for unpaid rent, and the refund due.
- **Rent Outstanding report** - aging buckets (0-30 / 31-60 / 61-90 / 90+) per tenant and room.
- **Import** - rooms and tenants from the Excel/CSV sheets landlords already keep. Every row is checked
  first with all the normal validations; bad rows are reported and skipped.
- **Export** - *Settings > Download all data*: everything entered, as one Excel workbook.
- **Rent Manager role** - full access to the app without System Manager.
- **Rent Management Settings** - rent due day and monthly invoicing (draft or submitted on the 1st of
  every month), online collection, reminders, WhatsApp, electricity rate, landlord details and agreement
  defaults and terms.

### Web app for managers (`/rent`)

A Vue 3 + Tailwind app at **`https://<site>/rent`** for users with the *Rent Manager* or *System Manager*
role, with a building switcher at the top:

- **Dashboard** - occupancy, collected vs invoiced, outstanding and overdue rent, 6-month chart.
- **Rooms** and **Buildings** - every room and bed with its tenant and dues; allot, invoice or vacate.
- **Tenants** - profile, current stay, notice, rent changes, agreement download, and an invite to the
  tenant app.
- **Requests**, **Import**, **Invoices**, **Payments** (including payments tenants reported, to confirm),
  **Deposits**, **Electricity**, **Outstanding**, **Expenses** and **Profit & loss**.
- **Settings** - all the settings above. Secret keys are write-only: they are never sent to the browser.
- **Subscription** (`/rent/billing`) - plan, usage, payments, GST invoices and automatic renewal.
- **SaaS** (`/rent/saas`) - on your control site only: all customers and revenue.

The frontend talks to the whitelisted methods in `rent_management/api.py`, which run every change through
the regular DocType validations. `bench build` builds it. To work on it with hot reload:

```bash
cd apps/rent_management/frontend
yarn install
yarn dev   # http://localhost:8080/rent/, proxies API calls to the Frappe server on :8000
```

Log in on the Frappe server first. The dev server can't inject a CSRF token, so set `"ignore_csrf": 1` in the
site's `site_config.json` while developing (never in production).

### Tenant app (`/tenant`)

Managers invite a tenant from their profile; the tenant gets an email to set a password and lands on
**`https://<site>/tenant`** (a Website User with the *Rent Tenant* role, no access to the desk or `/rent`).
Tenants can see their stay and dues, pay online or report a UPI payment, download invoices and their
agreement, raise and follow requests, and give notice. Every call only reaches the tenant's own records.

### Listing page and bookings (`/stay`)

Turn on *Settings > Listing page and bookings* to publish a page of your buildings at
**`https://<site>/stay`**, with a page per building (`/stay/sunrise-pg`). It shows the building's photo,
description, amenities, who it's for, food, a map link, and each room type with its rent, deposit and
**live free beds**. Shared on WhatsApp, the link shows the building's photo and description.

- Visitors **enquire** or **book a visit** (a day and time). Bots are kept out by a hidden field and rate
  limits.
- They can **hold a bed** by paying a token (*Token to hold a bed*, e.g. ₹2,000) straight to the landlord:
  online with a Razorpay payment link (the landlord's own keys, above), or by UPI QR. For UPI they enter
  the reference, and the manager confirms it. A held bed no longer shows as free.
- Every enquiry is a **Rent Lead** in **Leads** (`/rent/leads`), and managers are emailed and notified.
  Leads go New, Contacted, Visit Scheduled, Visited, Booked, then Moved In or Lost (with a reason).
  Managers add walk-ins and phone calls too, call or WhatsApp the lead, record a token paid in cash, or
  send a booking link to pay it.
- **Move in** makes the tenant profile and allots the bed in one step. A paid token is recorded as rent:
  on the first invoice, and the next one when moving in late in the month leaves the first one smaller.
- Token payments are picked up from the return page, the landlord's Razorpay webhook (the same URL as
  for rent, event `payment_link.paid`) and a daily check.

Building details for the page are under *Buildings > Edit > Listing page*.

### Tenant self check-in (`/checkin`)

On a tenant's profile, **Send check-in link** opens WhatsApp with a link for them (it is emailed too
when email is set up). On their phone, without logging in, the tenant:

1. fills in their details: date of birth, father's or guardian's name, address, work, and an emergency
   contact;
2. enters their Aadhaar number and uploads a photo of the card and a photo of themselves (private files);
3. reads their rental agreement and signs it by typing their name, ticking that they agree and entering a
   one-time code. The code goes by WhatsApp when the site sends WhatsApp (template `rent_signing_code`,
   category *Authentication*, body "{{1}} is your code to sign your rental agreement."), else by email.
   With neither, they sign with their typed name.

The **Tenant Check-in** keeps the proof: the agreement exactly as signed, its SHA-256 fingerprint, the
time, IP address and device, and where the code was sent. The agreement PDF then shows "Signed
electronically" instead of a signature line. Links expire after 14 days. The tenant app shows "Finish
your check-in" while one is open, and managers are notified when details come in and when it is signed.

**Police verification form**, on the tenant's profile: a PDF with their photo, full Aadhaar number,
addresses, work, emergency contact, the tenancy and the landlord's details, to submit at the police station
or on the state police portal. Printing it is logged on the tenant, as it shows the full Aadhaar number.

### Room checklists (move-in and move-out)

Each room has a list of **items in the room** (*Rooms > Edit*): bed, mattress, cupboard, chair, fan,
keys..., with quantities and a replacement cost. New rooms start with the usual furniture.

- **Move-in checklist** (tenant's profile > Room checklists): the condition of every item (Good, Fair,
  Damaged, Missing), notes and a photo per item. Once completed it is printed in the rental agreement
  ("Room condition at move-in"), so the tenant agrees to it when they sign at check-in. After that it can't
  be changed.
- **Move-out checklist**: starts from the move-in condition of each item. Damaged items are charged what
  the manager enters, missing ones their replacement cost. When the deposit is settled, these charges are
  filled in as deductions (Damages, or Lost Keys for keys). Once settled, the checklist can't be changed.

Every checklist is a **Room Inspection** with its items and photos (private files).

### Food and mess

Tick *Food included* on a building (*Buildings > Edit > Listing page*) and choose the meals it serves
(breakfast, lunch, dinner), their times, and until how many hours before a meal tenants can skip it.

- **Meal plans**, per stay (tenant's profile > Current stay > Food): *Included in rent* (the default in a
  building with food), *Paid monthly* (added to every rent invoice as a Food charge, for the days stayed)
  or *No meals*.
- **Weekly menu** on the **Food** page, shown to tenants in the tenant app.
- **Skipping meals:** tenants tap a meal in the tenant app (Food tab) to skip it, up to the cutoff;
  managers can mark one for them any time.
- **The kitchen count** on the Food page: for today or tomorrow, how many to cook for at each meal and who
  is skipping.
- **Food cost:** this month's *Food & Groceries* expenses divided by the meals actually served, per meal
  and per tenant per month.

### Hostel register

The **Register** page (under Property) keeps the warden's books. Set when the gate closes and until when
visitors are allowed on each building (*Buildings > Edit > Listing page*).

- **Night attendance:** every tenant staying that night, to mark *Present*, *Late* or *Absent* (with a
  note), then *Save attendance*. Tenants on approved leave are already marked *On Leave*. Someone absent
  without leave stands out, with buttons to call them and to WhatsApp their emergency contact. Earlier
  nights are a tap away; attendance can't be taken for a night that hasn't come.
- **Leave:** tenants ask from the tenant app (*Home > Going away or having a visitor?*) and managers are
  notified; the request waits under *Asking for leave* to approve or reject. Leave a manager adds is
  approved straight away. Approved leave skips the tenant's meals on those days (so the kitchen count
  drops); rejecting or cancelling it brings them back.
- **Visitors:** *Visitor at the gate* checks someone in (who they visit, why, staying overnight), *Left*
  checks them out, and *Inside now* lists who is in the building. Tenants can tell the warden in advance
  who is coming, which shows under *Expected* until the visitor arrives. Check-ins after visiting hours
  (and not overnight) are flagged.

### Staff and salaries

The **Staff** page (under Property) keeps who works at each building and pays them.

- **Staff:** name, role (warden, cook, cleaner, security...), the building their salary is counted
  under, monthly salary, the day of the month it's paid, and their UPI ID or bank account.
- **Salaries:** every month, *Prepare salaries* makes a slip for everyone who worked that month,
  pro-rated if they joined or left during it. Enter days off without pay, a bonus or a deduction, then
  *Pay* (date, mode, UTR). Paid salaries can be sent as a payslip on WhatsApp, and undone if entered by
  mistake. On each person's pay day, managers get a reminder if last month's salary isn't paid yet.
- **Advances:** money given early is taken back from the next salaries, all at once or a fixed amount
  a month (untick *Recover advances* on a slip to skip a month).
- **Expenses:** an advance is a *Salaries* expense the day it's given, and a salary the day it's paid
  (less what it recovered), so profit and loss shows what each building really spends on staff. These
  expenses can only be changed from the Staff page.

### Staff logins (limited access)

Give a staff member their own login to the manager app on the **Staff** page: *Give an app login* on
their card. Enter their email, tick what they can use, and send them the link to set a password (by
email automatically, or *Send it on WhatsApp*).
- **Areas:** rooms and tenants; rent and payments; night attendance, leave and visitors; requests
  and repairs; food and menu; leads and bookings; electricity readings; expenses; the notice board.
  Their role pre-ticks a sensible set (a warden gets rooms, payments, the register, requests,
  electricity and notices; a cook gets food).
- **Building:** a login is for the building they work at, unless *All buildings* is ticked.
- **Never for staff:** profit and loss, the monthly report, staff and salaries, deposits, buildings,
  import and export, settings, the subscription, Aadhaar numbers, and making or deleting invoices.

Staff open the app at `/rent` (and install it on their phone). They see a **Today** page with their
quick actions: attendance status, leave requests, visitors inside, payments to confirm, open requests
and the kitchen count. They get the notifications of their areas for their building. Change a login
or *Remove login* (they're logged out at once) from the same card. Staff logins don't count towards
the plan's user limit, which is for managers.

The server enforces this, not just the menus. Every endpoint checks the login's areas, a one-building
login can only ask for its building, and Frappe's record permissions (the `Rent Staff` role, no Desk)
only show the records of their areas and building. See `rent_management/access.py`.

### Cash book

**Cash book** (under Billing) tracks who holds the cash.
- **Collected:** a cash payment is held by whoever recorded it, or confirmed it if the tenant reported it.
- **Spent:** a cash expense comes out of whoever recorded it, including salaries and advances paid in
  cash.
- **Handing over:** *Hand over cash* sends an amount to a manager (or another staff login) with a
  note. They get a notification and tap *I have it* or *Didn't get it*. The money moves only once
  they confirm, and until then it shows as on its way. The one handing over can cancel while it waits.
- **Managers** see what each person holds now (collected, spent, received, handed over), what was
  handed to them, and a day-by-day book of every cash movement for any dates and building. Someone
  who paid more than they collected shows as owed money.
- **Staff logins** with payments or expenses see their own cash only.

Cash recorded before this was added counts as held by whoever recorded it.

### Activity log

**Activity** (under Overview, managers only) shows who did what and when, in plain words. Filter by
person, building, type and dates. For example: "Manjunath Gowda recorded ₹5,000 in cash from Deepak
Reddy for October 2026".

It records:
- **Payments:** recorded, received online, cancelled, and reported payments turned down
- **Invoices:** issued, cancelled and deleted; a month's generation as one entry; late fees waived or
  charged again; splits into instalments
- **Stays and tenants:** move-ins and move-outs, rent changes, notices given and withdrawn, deposits
  collected and settled, tenants added and deleted
- **Expenses, staff and cash:** expenses added, changed and deleted; salaries paid and undone, advances,
  staff logins given, changed and removed; cash handed over and confirmed
- **The rest:** leave approved or turned down, notices published and deleted, settings changes (old →
  new, with passwords and keys only noted as changed), and every view of an Aadhaar number (*Privacy*)

Entries can't be edited. Only a System Manager can delete them, and they stay when the record they
name is cancelled or deleted.

### Rent receipts for income tax (HRA)

Salaried tenants claim HRA with rent receipts. In the tenant app, **Bills > Rent receipts for HRA**
lists each month they paid rent in a financial year (April to March). They can download a receipt
for one month or one for the whole year. Managers get the same on the tenant's page (**Rent
receipts** tab).

A receipt shows:
- the tenant, and who the rent is paid to with their PAN and address
- the property and room
- each month's rent, with when and how it was paid (UTRs included)
- the total in figures and words
- a revenue stamp box when a cash payment is over ₹5,000
- the landlord's signature if you add one

Only rent counts, less any discounts and up to what was paid. Electricity, food and late fees are
left out.

Set it up in **Settings > Rental agreements**: *Landlord PAN* and *Signature on rent receipts*. For a
building owned by someone else, add the owner's name, PAN and address on the building (*Buildings >
Edit*). Its receipts then name the owner. When a tenant's rent is over ₹1,00,000 in a year and no
PAN is set, both apps warn, because employers need the landlord's PAN for that.

### Police verification

Many cities ask landlords to submit a verification form for each tenant to the local police. Turn
on **Settings > Police verification** and choose how many days after moving in it's due (default 7).
Set each building's police station under *Buildings > Edit*.

**Verification** (under Property) tracks each tenant:
- **Overdue** (past the days), **to submit**, **with the police** (flagged after 30 days), **done**.
- **Form** prints the verification form, filled in from their check-in.
- **Mark submitted:** the date, police station, acknowledgement number and a photo of the
  acknowledgement.
- **Mark verified:** the date and the stamped copy (photo or PDF). Or mark it *not needed*.

Every new stay starts as *to submit* once tracking is on. Earlier tenants aren't tracked until you
click *Track* on their page. Managers and wardens (logins with rooms and tenants) are told on the
day each one is due, and every Monday what's overdue and still with the police. The tenant's page
shows the status too.

### Tenant documents

The **Documents** tab on a tenant's page keeps their papers: PAN, passport, visa, driving licence,
voter ID, offer letter, employee or college ID, and more. Each is a photo or PDF (5 MB at most) with
an optional number, issue date and expiry date. The Aadhaar card from check-in and the police
verification papers show here too. Aadhaar numbers are never stored on a document, only the last
four digits.

Tenants add theirs under **Profile > My documents** in the tenant app. They can remove only what
they added. Files are private: tenants open theirs through the app, and managers from the tenant's
page. Managers and wardens are told 30 days before a document expires, and on the day.

### Collecting rent online

Rent goes straight into the landlord's own account, set up in *Settings > Online rent collection*:

- **UPI** - enter the UPI ID. Invoices and the tenant app show a UPI QR / link for the exact balance. When a
  tenant reports a payment, the manager confirms it under *Payments*.
- **Razorpay payment links** - enter the landlord's own Razorpay keys. Each invoice gets a payment link
  for its balance, and the payment is recorded as a Rent Payment automatically (when the tenant returns to
  the app, by the daily reconcile job, or by the webhook). Optional webhook in the landlord's Razorpay
  account, event `payment_link.paid`:
  `https://<site>/api/method/rent_management.rent_collection.razorpay_webhook` with its secret in Settings.

### Late fees, early payment discounts and instalments

Set them up in **Settings > Late fees and discounts**.

- **Late fee:** a fixed amount once, or an amount for every day late (with an optional maximum), added
  to an unpaid invoice once the grace days after its due date are over. A daily job adds it and lets it
  grow while the invoice is unpaid. *Waive* it on any invoice (and *charge it* again).
- **Discount for paying early:** an amount or a percent of the rent, if the invoice is paid in full by
  the due date (or some days before). Each invoice keeps the offer it was made with. While the offer
  stands, the tenant app, UPI QR and payment link ask for the discounted amount, and recording that
  amount settles the invoice. Paying late, or cancelling the payment, takes the discount back off.
- **Instalments:** on an unpaid invoice, *Split into instalments* (2 to 4 parts, or your own dates and
  amounts). Payments go to the parts in order. The next unpaid part decides when the invoice is overdue,
  when reminders go out and when a late fee starts. Tenants see the schedule on their bill. Split
  invoices get no early payment discount.

Late fees and discounts show on the invoice, the printed invoice and the tenant's bill, and count as
rent invoiced in profit and loss.

### Monthly report for the owner

**Monthly report** (under Overview) shows how a month went, for all buildings or the one chosen at
the top:
- money collected against invoiced, money spent and where it went, and profit, each compared with
  the month before
- beds taken, a line per building, and who still owes and since when
- who moved in and out, who leaves in the next 30 days, new enquiries and open requests

*Open in WhatsApp* opens the summary as a ready message to the owner. That needs no WhatsApp
account, only WhatsApp on the phone or computer. To have it sent automatically, turn on
**Settings > Monthly summary for the owner**. Choose the day (last month's summary is sent once that
day) and the owner's WhatsApp number (default: the landlord phone) and email. It's sent with the same
WhatsApp account and email as reminders; the WhatsApp template is `rent_owner_summary` (see
`owner_summary.py`).

### Referrals

Turn on **Settings > Referrals** (it needs the listing page) and set the reward for the tenant who
refers (default ₹1,000 off their next rent) and the friend's discount (default ₹500 off their first
rent).

- **Tenants** share their link from the tenant app (*Refer a friend*): on WhatsApp, by copying it,
  or with the phone's share sheet. The link opens the listing page with their code (`/stay?ref=CODE`)
  and a note of who sent the friend and the discount they get.
- **An enquiry** through the link is a lead from *Referral*, referred by that tenant. Managers can
  also mark a walk-in or phone lead as referred by a tenant. Referring yourself (same mobile) doesn't
  count, nor does a friend someone else already referred.
- **When the friend moves in**, their first rent invoice gets the discount. **When they've paid a rent
  invoice in full**, the reward is earned: the referrer is told (WhatsApp template
  `rent_referral_reward`, see `referrals.py`) and managers get a notification. The reward comes off the
  referrer's next rent invoice. If they have moved out, *Paid in cash* records it as a Marketing
  expense.
- Discounts and rewards are *Referral Credit* lines on the invoice. A cancelled or deleted invoice
  gives them back, and they never take an invoice below zero (they wait for the next one).
- **Leads > Referrals** lists every referral, what's been rewarded and what's waiting.

### Phone app (install from the browser)

The manager app (`/rent`) and the tenant app (`/tenant`) install like phone apps from the browser,
with no app store. They open full screen from the home screen with their own icon.
- **Install popup:** on a phone, both apps ask to be installed every time they're opened in the
  browser. Android gets an *Install* button (Chrome's own dialog). iPhone gets the steps (Share >
  *Add to Home Screen*) with an arrow to Safari's Share button. Inside WhatsApp's or Instagram's browser,
  it asks to open the page in Safari or Chrome first. *Not now* hides it until the next visit, and
  *Don't ask again* hides it on that phone for good.
- **Installing:** on Android (Chrome), use the *Install the app* button (sidebar, or **Settings >
  This phone**; tenants have it on their Profile) or the browser menu's *Install app*. On iPhone
  (Safari), use Share > *Add to Home Screen*.
- **Shortcuts:** long-press the manager app's icon for *Record payment*, *Night attendance*, *Visitor at
  the gate* and *Add lead*. On a phone, the dashboard shows the same four as buttons.
- **Weak signal:** pages show the last data they loaded, with an "offline" note, and saving says so
  when there's no signal. Logging out removes the data kept on the phone.
- **Phone notifications** for managers: turn them on per phone in **Settings > This phone**. Every app
  notification (new leads and bookings, leave requests, payments to confirm, requests, notices, salaries
  due, referral rewards) then also shows on the phone, even when the app is closed, and tapping it
  opens the right page. On iPhone this needs iOS 16.4 or later and the app added to the home screen
  first.

These use the site's own Web Push keys, made the first time a phone turns notifications on (Settings
> Phone notifications). The push carries no data, the phone fetches what's new from the site, so no
push service account or library is needed. The site must be served over HTTPS (localhost works for
testing). The manifest and service worker are served by `rent_management/pwa.py` at
`/rent/manifest.webmanifest` and `/rent/sw.js` (and the same under `/tenant/`).

### Notice board

**Notices** (under Property) are announcements to tenants: water or power cuts, repairs, pest
control, house rules, a festival dinner.
- **Writing one:** start from a template or write your own: who it's for (one building or all), a
  category, the title and message, and optionally *pin to the top* and *show until* a date. *Save
  draft* or *Publish*.
- **Publishing** puts it on the notice board of every tenant currently staying there:
  - in the tenant app, behind a bell with an unread count, and as a card on Home
  - as a phone notification, for tenants who turned them on (on the Notices page, or with the app
    installed)
  - if ticked, also on WhatsApp (template `rent_notice`, see `notices.py`; WhatsApp charges per
    message) and by email
- **Seen by:** each notice shows how many tenants have seen it ("Seen by 15 of 23"). *Take down*
  removes it from the board, and it can be published again later.

Publishing sends in a background job, so the site's workers must be running (`bench start`, or
supervisor in production).

### Reminders and receipts (WhatsApp and email)

A daily job sends rent reminders before the due date, on the due date and while overdue (interval and
limit in Settings), and a receipt for every payment. Every message is in the **Rent Message Log**.

- **Email** uses the site's default outgoing Email Account (or `mail_server` in the site config).
- **WhatsApp** uses the WhatsApp Cloud API. Either the landlord enters their own WhatsApp Business phone
  number ID and token in Settings, or you provide one number for all customers whose plan includes
  WhatsApp, with `whatsapp_phone_number_id` and `whatsapp_token` in `common_site_config.json`.
  WhatsApp only sends approved templates. Create these in WhatsApp Manager (category *Utility*):

  ```
  rent_reminder        Hello {{1}}, your rent of {{2}} for {{3}} at {{4}} is due on {{5}}. {{6}}
  rent_overdue         Hello {{1}}, your rent of {{2}} for {{3}} at {{4}} was due on {{5}} and is still unpaid. {{6}}
  rent_receipt         Hello {{1}}, we have received {{2}} for your rent for {{3}} at {{4}}. Balance due: {{5}}. Thank you!
  rent_request_update  Hello {{1}}, your request "{{2}}" is now {{3}}. {{4}}
  ```

  Optional: `whatsapp_templates` to use other template names (`{"rent_reminder": "my_reminder"}`),
  `whatsapp_language` (`en`) and `whatsapp_api_version` (`v21.0`).

### Selling it as SaaS

Every customer gets their own site on your bench. They sign up on your website, start on a free trial,
and pay monthly or yearly through **your** Razorpay account.

#### Plans and subscriptions

| Plan    | Monthly | Yearly  | Beds      | Buildings | Manager logins | WhatsApp, profit report |
| ------- | ------- | ------- | --------- | --------- | -------------- | ----------------------- |
| Starter | ₹499    | ₹4,990  | 30        | 1         | 2              | -                       |
| Growth  | ₹1,499  | ₹14,990 | 120       | 3         | 5              | Yes                     |
| Pro     | ₹3,999  | ₹39,990 | unlimited | unlimited | unlimited      | Yes                     |

- **Trial** - a new site gets a 14-day trial of the Growth plan.
- **Limits** - beds, buildings and Rent Manager users are enforced; a downgrade below current usage is
  refused.
- **Paying** - Razorpay Checkout (UPI, cards, netbanking) at `/rent/billing`, verified on the server
  (signature, captured status and amount). Paying early adds the new period after the current one;
  switching plan starts it today and turns the unused days of the old plan into extra days.
- **Automatic renewal** - with *Renew automatically* ticked, Checkout sets up a UPI AutoPay or card
  mandate (Razorpay Subscriptions) and Razorpay charges every month or year by itself. It can also be
  turned on later for the plan already paid for (first charge when it ends) and turned off at any time.
  Charges are recorded from the Checkout callback, the webhook or the daily job, whichever comes first,
  including mandates whose Checkout tab was closed. Renewal reminders aren't sent while it is on.
- **Lapsing** - after the paid period there are 3 grace days (*Past Due*), then the site is **read-only**:
  everything stays visible, nothing can be changed, and monthly invoicing pauses. Rent Managers get
  reminder emails 7, 3 and 1 days before the end.
- **GST tax invoices** - every payment gets a tax invoice with its own number series per customer
  (e.g. `SHARMA/2627/0001`), CGST + SGST or IGST by the customer's state, and their GSTIN when they enter
  it under *Billing details*. Emailed to them and downloadable from `/rent/billing`.
- **Records** - every payment is a **Rent Subscription Payment**; the current state is the
  **Rent Subscription** single. Customers can't edit either.

Plans and prices can be changed without a release with `rent_subscription_plans` (see below);
`rent_subscription_enabled: 0` switches subscriptions off on a site (e.g. your demo site).

```json
"rent_subscription_plans": {
  "starter": {"title": "Starter", "monthly": 499, "yearly": 4990, "max_beds": 30, "max_properties": 1,
              "max_users": 2, "whatsapp": 0, "profit_report": 0,
              "description": "For a single PG", "features": ["Up to 30 beds", "2 manager logins"]},
  "pro": {"title": "Pro", "monthly": 3999, "yearly": 39990, "max_beds": 0, "max_properties": 0,
          "max_users": 0, "whatsapp": 1, "profit_report": 1}
}
```

`0` means unlimited.

#### Setting up the bench (once)

```bash
# your Razorpay account, shared by all customer sites (Dashboard > Account & Settings > API Keys)
bench set-config -g razorpay_key_id rzp_live_xxxxxxxx
bench set-config -g razorpay_key_secret xxxxxxxx
bench set-config -g razorpay_webhook_secret xxxxxxxx
bench set-config -g rent_support_email support@yourdomain.com

# your business, for the GST invoices
bench set-config -g --parse rent_vendor '{"name": "Your Company Pvt Ltd", "gstin": "29ABCDE1234F1Z5",
  "address": "...", "email": "billing@yourdomain.com", "phone": "...", "sac": "998314"}'
```

Plan prices include GST by default (`rent_prices_include_gst: 1`, rate `rent_gst_rate: 18`). Without a
GSTIN, invoices are plain invoices without tax.

#### Your control site

One site on the bench is yours: it shows all customers and revenue, hosts the signup page and receives
the Razorpay webhooks.

```bash
bench new-site admin.yourdomain.com --install-app rent_management
bench --site admin.yourdomain.com set-config rent_control_site 1
bench --site admin.yourdomain.com set-config rent_subscription_enabled 0

# every customer site reports to it once a day (and after each payment), signed with this secret
bench set-config -g rent_control_url https://admin.yourdomain.com
bench set-config -g rent_control_secret "$(openssl rand -hex 32)"
```

- **`/rent/saas`** (System Managers of the control site) - MRR and ARR, customers by status, trial
  conversion, trials ending, renewals due, past-due customers, sites that stopped reporting, signups per
  month and the full list (**SaaS Customer**).
- **Razorpay webhook** - in your Razorpay account, add one webhook to
  `https://admin.yourdomain.com/api/method/rent_management.saas.razorpay_webhook` with the events
  `order.paid`, `payment.captured` and all `subscription.*` events, and the secret from above. The control
  site checks the signature and forwards each event to the customer site it belongs to. If the sites are
  on the same server and shouldn't call themselves over the internet, set `rent_webhook_forward_base`
  (e.g. `http://127.0.0.1:8000`) on the control site. The webhook is a backup: payments are also
  confirmed by the Checkout callback and checked by a daily job.

#### Self-serve signup (`/signup` on the control site)

Visitors pick a plan, their business name and an address like `sharma.yourdomain.com`, and confirm their
email. A background job then creates their site (`bench new-site ... --install-app rent_management` and
`bench --site ... rent-onboard ...`): their Rent Manager login, billing details, first building, GST
invoice prefix and the trial. The page shows progress and a link to set their password, which is also
emailed. Failed signups (**SaaS Signup**) can be retried from the desk.

```bash
bench --site admin.yourdomain.com set-config rent_signup_domain yourdomain.com
bench set-config -g root_password <mariadb root password>   # so new-site doesn't prompt
# optional
bench --site admin.yourdomain.com set-config rent_bench_command /usr/local/bin/bench
bench --site admin.yourdomain.com set-config rent_signup_post_provision "sudo -n /usr/local/bin/rent-new-site {site}"
```

Requirements:

- An outgoing Email Account on the control site (signups are refused without one, as the email can't be
  confirmed). `rent_signup_skip_verification: 1` skips the email for testing only.
- A worker for the `long` queue (`bench start` / supervisor run one).
- DNS: a wildcard record `*.yourdomain.com` pointing to the server, and `bench config dns_multitenant on`.
- nginx and SSL: new sites need `bench setup nginx` and a certificate. Use a wildcard certificate for
  `*.yourdomain.com` (certbot with a DNS challenge) in your nginx config, and run
  `bench setup nginx --yes && sudo systemctl reload nginx` from the post-provision command (which gets the
  new site's name as `{site}`; allow it in sudoers without a password).
- `rent_signup_scheme: "http"` only for local testing (default `https`).

#### Onboarding a customer by hand

```bash
bench new-site sharma.yourdomain.com --install-app rent_management
bench --site sharma.yourdomain.com rent-onboard --email owner@sharma.com --full-name "Ravi Sharma" \
  --business "Sharma PG" --phone 9876543210 --city Pune --invoice-prefix SHARMA \
  --host-name https://sharma.yourdomain.com
```

It prints a link to set the password. (`bench --site <site> rent-add-manager <email>` adds more managers.)
Give customers the **Rent Manager** role only, never System Manager or the Administrator password, so they
can't change their own subscription.

#### Managing subscriptions

```bash
bench --site <site> rent-subscription                     # status, plan, usage
bench --site <site> rent-subscription --plan growth --cycle Yearly --amount 14990 --reference NEFT123
bench --site <site> rent-subscription --plan pro --until 2027-03-31    # custom or free deal
bench --site <site> rent-subscription --restart-trial
```

#### Backups

```bash
bench rent-backup-all --with-files --remote b2:my-bucket/rent   # every site, copied off the server
```

It backs up every site on the bench and copies the backups with [rclone](https://rclone.org) to
`<remote>/<site>` (or to `rent_backup_remote` from `common_site_config.json`); local backups older than
`--keep-days` (7) are removed. Run it from cron every night:

```
0 2 * * * cd /home/frappe/frappe-bench && bench rent-backup-all --with-files >> logs/rent-backup.log 2>&1
```

### Configuration reference

All keys go in `common_site_config.json` (`bench set-config -g`) or a site's `site_config.json`
(`bench --site <site> set-config`).

| Key | Where | What |
| --- | --- | --- |
| `razorpay_key_id`, `razorpay_key_secret` | all sites | Your Razorpay account, for subscription payments |
| `razorpay_webhook_secret` | all sites | Secret of your Razorpay webhook |
| `rent_razorpay_plan_ids` | all sites | Use Razorpay plans you made yourself for automatic renewal: `{"growth:Monthly": "plan_xxx"}`. By default they are created when first needed |
| `rent_subscription_enabled` | site | `0` to switch subscriptions off (your control and demo sites) |
| `rent_subscription_plans` | all sites | Plans, prices, limits and features |
| `rent_trial_days`, `rent_trial_plan` | all sites | Trial length (14) and plan (`growth`) |
| `rent_grace_days` | all sites | Days after the paid period before the site turns read-only (3) |
| `rent_subscription_currency` | all sites | `INR` |
| `rent_subscription_brand` | all sites | Your product name, in emails, Checkout and the signup page |
| `rent_support_email` | all sites | Shown to customers who need help paying |
| `rent_vendor` | all sites | Your business on GST invoices: `name`, `gstin`, `state`, `address`, `email`, `phone`, `sac` |
| `rent_gst_rate`, `rent_prices_include_gst` | all sites | GST rate (18) and whether plan prices include it (1) |
| `rent_invoice_prefix` | site | Prefix of the customer's invoice numbers (set by signup / `rent-onboard`) |
| `rent_control_site` | control site | `1` on your control site |
| `rent_control_url`, `rent_control_secret` | all sites | Where customer sites report to, and the shared secret |
| `rent_webhook_forward_base` | control site | Forward webhooks to this address with a Host header, instead of `https://<site>` |
| `rent_signup_domain` | control site | Customer sites become `<name>.<domain>`; signups are closed without it |
| `root_password` | bench | MariaDB root password, so `bench new-site` doesn't prompt |
| `rent_bench_command` | control site | Path to `bench` if it isn't on the worker's PATH |
| `rent_signup_post_provision` | control site | Command run after a site is created, `{site}` is its name (nginx, SSL...) |
| `rent_signup_scheme` | control site | `https` (default), `http` for local testing |
| `rent_signup_skip_verification` | control site | `1` to skip the email confirmation (testing only) |
| `whatsapp_phone_number_id`, `whatsapp_token` | all sites | Your WhatsApp number for customers whose plan includes WhatsApp |
| `whatsapp_templates`, `whatsapp_language`, `whatsapp_api_version` | all sites | Template names, language (`en`), Graph API version (`v21.0`) |
| `rent_backup_remote` | bench | rclone remote for `rent-backup-all` |

### Demo data

To see the app with realistic data, make a demo site and fill it:

```bash
bench new-site demo.localhost --install-app rent_management
bench --site demo.localhost rent-demo-data          # --password to choose the demo password
bench --site demo.localhost serve --port 8001       # or add it to your nginx / hosts file
```

It creates a PG business in Bengaluru with six months of history, dated up to today: 3 buildings,
16 rooms with shared beds, about 25 tenants, monthly invoices with electricity, payments (and a few
overdue), move-outs with deposit settlements, a tenant on notice, a rent increase, expenses, requests
and reminder messages. It prints two logins (password `demo@1234`): a Rent Manager for `/rent` and a
tenant for `/tenant`. It refuses to run on a site that already has rooms or tenants.

### Workflow

1. Create a **Rent Property** (building), **Tenant Space Types** and **Tenant Spaces** (rooms and beds),
   or import them.
2. Create a **Tenant**.
3. Create and submit a **Tenant Space Allotment** for the tenant and room.
4. Rent invoices are generated every month (or use *Create > Rent Invoice* on the allotment).
5. Submit the invoice; the tenant pays online or you record a **Rent Payment**.
6. When the tenant gives notice, record it on the allotment; click **Vacate** when they move out. The last
   invoice is pro-rated to the vacate date.
7. Tick **Deposit Collected** on the allotment when you receive the deposit. After vacating, use
   *Create > Deposit Settlement* to settle it.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app rent_management
bench setup-chrome
```

PDFs (agreements, invoices, rent receipts, the police verification form) are made with Chrome, which
runs on Linux, Intel Macs and Apple-chip Macs alike. `bench setup-chrome` downloads it into the bench
once; otherwise it's downloaded the first time a PDF is made, or set `chromium_path` in
`common_site_config.json` to use one you have. If Chrome can't start, wkhtmltopdf is used instead.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/rent_management
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
