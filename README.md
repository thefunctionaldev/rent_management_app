### Rent Management System

Rent Management System

A [Frappe](https://frappe.io) app to manage rooms, tenants, monthly rent invoices and rent collection.

### Features

- **Tenant** - contact, personal (with Aadhaar checksum validation) and professional details.
- **Tenant Space Type / Tenant Space** - room types with standard rent and security deposit, and rooms with live
  occupancy status (Available / Reserved / Occupied / Under Renovation).
- **Tenant Space Allotment** - allots a room to a tenant. Submitting it marks the room Occupied; the **Vacate**
  button records the move-out date and frees the room. A room cannot be allotted to two tenants at once.
- **Tenant Rent Invoice** - one invoice per allotment per month. Rent is pro-rated for the days actually occupied
  (move-in and move-out months), extra charges (electricity, water, maintenance...) and a discount can be added,
  and the invoice tracks paid / outstanding amount with a status of Unpaid, Partly Paid, Paid or Overdue.
- **Rent Payment** - records a payment (Cash, UPI, Bank Transfer, Cheque...) against an invoice and updates its
  outstanding amount.
- **Security Deposit Settlement** - settles the deposit after the tenant vacates: record deductions (damages,
  cleaning...), optionally use the deposit to pay off unpaid rent (posted as Rent Payments with mode
  *Security Deposit*), and see the refund due to the tenant or the balance they still owe.
- **Rent Outstanding report** - unpaid invoices with days overdue, aging buckets (0-30 / 31-60 / 61-90 / 90+),
  totals and a chart. Filter by tenant, room or overdue only.
- **Rent Manager role** - full access to everything in the app without needing System Manager. Assign it to the
  people who run the property.
- **Rent Management Settings** - rent due day, and automatic monthly invoicing. On the 1st of every month an
  invoice is created for each active allotment (as draft, or submitted). Use **Generate Invoices Now** to run it
  for any month. A daily job marks unpaid invoices past their due date as Overdue.

### Web app (`/rent`)

Besides the Frappe desk, the app ships a Vue 3 + Tailwind frontend for property managers at
**`https://<your-site>/rent`**. It uses the normal Frappe login and is available to users with the
*Rent Manager* or *System Manager* role.

- **Dashboard** - occupancy, collected vs invoiced, outstanding and overdue rent, 6-month collection chart,
  overdue invoices and recent payments.
- **Rooms** - every room as a card with its status, tenant and dues; allot, invoice or vacate in one click.
- **Tenants** - searchable list and a profile page with the current stay, invoices, payments and stay history.
- **Invoices** - filter by status / month, generate the month's invoices, create invoices with extra charges,
  submit drafts, record payments, print, and send a WhatsApp reminder.
- **Payments**, **Deposits** (collect, then settle with a live refund preview) and **Outstanding** (aging buckets).

The frontend talks to the whitelisted methods in `rent_management/api.py`, which run every change through the
regular DocType validations.

`bench build` builds the frontend automatically. To work on it with hot reload:

```bash
cd apps/rent_management/frontend
yarn install
yarn dev   # http://localhost:8080/rent/, proxies API calls to the Frappe server on :8000
```

Log in on the Frappe server first. The dev server can't inject a CSRF token, so set `"ignore_csrf": 1` in the
site's `site_config.json` while developing (never in production).

### Subscriptions (selling it as SaaS)

The app is sold as a hosted service: every customer gets their own site on your bench, starts on a
free trial and then pays monthly or yearly through Razorpay from **`/rent/billing`**.

- **Trial** - a new site (or an existing one after `bench migrate`) gets a 14-day trial of the Growth plan.
- **Plans** - Starter (15 rooms, 2 logins), Growth (60 rooms, 5 logins) and Pro (unlimited), monthly or
  yearly. Room and Rent Manager user limits are enforced; a downgrade below current usage is refused.
- **Paying** - Razorpay Checkout (UPI, cards, netbanking). The payment is verified on the server
  (signature, captured status and amount) before the subscription is extended. Paying early adds the new
  period after the current one; switching plan starts the new plan today and turns the unused days of the
  old plan into extra days on the new one.
- **Lapsing** - after the paid period there are 3 grace days (*Past Due*), then the site is **read-only**:
  everything stays visible, but nothing can be created, changed or deleted, and monthly invoicing pauses.
  Rent Managers get reminder emails 7, 3 and 1 days before the end.
- **Records** - every payment is a **Rent Subscription Payment**; the current state is the
  **Rent Subscription** single. Neither can be edited by customers, only by Administrator.

#### Setting up the bench (once)

```bash
# Razorpay keys, shared by all customer sites (Dashboard > Account & Settings > API Keys)
bench set-config -g razorpay_key_id rzp_live_xxxxxxxx
bench set-config -g razorpay_key_secret xxxxxxxx
bench set-config -g rent_support_email support@yourdomain.com
```

Payments are confirmed by the checkout callback, and a daily job also checks Razorpay for orders whose
browser tab was closed before the callback ran, so a webhook is optional. To add one anyway (events
`order.paid` and `payment.captured`), point it at
`https://<customer-site>/api/method/rent_management.subscription.razorpay_webhook` and set
`bench set-config -g razorpay_webhook_secret xxxx`. Orders from other sites are ignored.

Optional overrides in `common_site_config.json` (or per site): `rent_trial_days` (14), `rent_trial_plan`
(`growth`), `rent_grace_days` (3), `rent_subscription_currency` (`INR`), `rent_subscription_brand`
(name in the payment window) and `rent_subscription_plans` to change plans and prices without a release:

```json
"rent_subscription_plans": {
  "starter": {"title": "Starter", "monthly": 499, "yearly": 4990, "max_rooms": 15, "max_users": 2,
              "description": "For a single PG", "features": ["Up to 15 rooms", "2 manager logins"]},
  "pro": {"title": "Pro", "monthly": 3999, "yearly": 39990, "max_rooms": 0, "max_users": 0}
}
```

`0` means unlimited. Set `rent_subscription_enabled` to `0` on a site to switch subscriptions off
there (e.g. your own demo site).

#### Onboarding a customer

```bash
bench new-site pg-sharma.yourdomain.com --install-app rent_management
bench --site pg-sharma.yourdomain.com rent-add-manager owner@sharma.com --first-name Ravi
```

The customer gets an email to set their password and logs in at `/rent`. Give customers the
**Rent Manager** role only, never System Manager or the Administrator password, so they can't change
their own subscription.

#### Managing subscriptions

```bash
bench --site <site> rent-subscription                     # status, plan, usage
bench --site <site> rent-subscription --plan growth --cycle Yearly --amount 14990 --reference NEFT123
bench --site <site> rent-subscription --plan pro --until 2027-03-31    # custom or free deal
bench --site <site> rent-subscription --restart-trial
```

### Workflow

1. Create **Tenant Space Types** and **Tenant Spaces** (rooms).
2. Create a **Tenant**.
3. Create and submit a **Tenant Space Allotment** for the tenant and room.
4. Rent invoices are generated every month (or use *Create > Rent Invoice* on the allotment).
5. Submit the invoice, then use *Create > Rent Payment* on it to record what the tenant paid.
6. When the tenant moves out, click **Vacate** on the allotment; the last invoice is pro-rated to the vacate date.
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
