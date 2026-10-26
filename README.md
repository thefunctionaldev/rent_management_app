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
- [Workflow](#workflow) · [Installation](#installation) · [Contributing](#contributing)

### Features

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

### Collecting rent online

Rent goes straight into the landlord's own account, set up in *Settings > Online rent collection*:

- **UPI** - enter the UPI ID. Invoices and the tenant app show a UPI QR / link for the exact balance. When a
  tenant reports a payment, the manager confirms it under *Payments*.
- **Razorpay payment links** - enter the landlord's own Razorpay keys. Each invoice gets a payment link
  for its balance, and the payment is recorded as a Rent Payment automatically (when the tenant returns to
  the app, by the daily reconcile job, or by the webhook). Optional webhook in the landlord's Razorpay
  account, event `payment_link.paid`:
  `https://<site>/api/method/rent_management.rent_collection.razorpay_webhook` with its secret in Settings.

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
```

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
