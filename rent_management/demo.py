# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Demo data: a PG business in Bengaluru with six months of history, to show the app.

    bench new-site demo.localhost --install-app rent_management
    bench --site demo.localhost rent-demo-data

Everything goes through the normal documents, in date order (move-ins, meter readings on the
1st, monthly invoices, payments, move-outs and deposit settlements), so the numbers add up on
every page. The data is the same every time (fixed random seed) and dated relative to today.
"""

import heapq
import random

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	add_months,
	date_diff,
	flt,
	get_datetime,
	get_first_day,
	get_last_day,
	getdate,
	nowdate,
)
from frappe.utils.password import update_password

from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS

SETTINGS = "Rent Management Settings"
ALLOTMENT = "Tenant Space Allotment"
INVOICE = "Tenant Rent Invoice"
MONTHS_OF_HISTORY = 6

LANDLORD = {
	"landlord_name": "Ravi Kumar",
	"landlord_phone": "9845012345",
	"landlord_address": "14, 5th Cross, Koramangala 4th Block, Bengaluru 560034",
	"upi_id": "sunrisepg@okicici",
	"upi_payee_name": "Sunrise PG",
	"electricity_rate": 9,
	"rent_due_day": 5,
	"default_agreement_months": 11,
	"default_lock_in_months": 3,
	"default_notice_days": 30,
	"default_rent_increase_percent": 5,
}

# name, abbr, address, pincode, who it's for, opened (days ago)
BUILDINGS = [
	("Sunrise PG", "SUN", "14, 5th Cross, Koramangala 4th Block", "560034", "Male", 900),
	("Green Villa Hostel", "GV", "221, 27th Main, HSR Layout Sector 2", "560102", "Female", 700),
	("Lakeview Residency", "LR", "9, 16th Main, BTM 2nd Stage", "560076", None, 80),
]

ROOM_TYPES = [
	{
		"type": "Single Room",
		"standard_rent": 14000,
		"security_deposit": 28000,
		"is_furnished": 1,
		"has_attached_bathroom": 1,
		"description": "Private room with attached bathroom",
	},
	{
		"type": "Double Sharing",
		"standard_rent": 9000,
		"security_deposit": 18000,
		"is_furnished": 1,
		"has_attached_bathroom": 1,
		"description": "Two beds, attached bathroom",
	},
	{
		"type": "Triple Sharing",
		"standard_rent": 6500,
		"security_deposit": 13000,
		"is_furnished": 1,
		"description": "Three beds, common bathroom on the floor",
	},
]

# building, room number, floor, room type, beds, has meter, rent (None: the room type's)
ROOMS = [
	("Sunrise PG", "101", "1", "Double Sharing", 2, 1, None),
	("Sunrise PG", "102", "1", "Double Sharing", 2, 1, None),
	("Sunrise PG", "103", "1", "Triple Sharing", 3, 1, None),
	("Sunrise PG", "104", "1", "Single Room", 1, 1, None),
	("Sunrise PG", "201", "2", "Double Sharing", 2, 1, 9500),
	("Sunrise PG", "202", "2", "Triple Sharing", 3, 1, None),
	("Sunrise PG", "203", "2", "Single Room", 1, 1, 15000),
	("Sunrise PG", "204", "2", "Double Sharing", 2, 1, None),  # under renovation
	("Green Villa Hostel", "G1", "Ground", "Double Sharing", 2, 1, 8500),
	("Green Villa Hostel", "G2", "Ground", "Triple Sharing", 3, 1, 6000),
	("Green Villa Hostel", "F1", "1", "Single Room", 1, 1, 13000),
	("Green Villa Hostel", "F2", "1", "Double Sharing", 2, 1, 8500),
	("Green Villa Hostel", "F3", "1", "Double Sharing", 2, 1, 8500),
	("Lakeview Residency", "L1", "1", "Single Room", 1, 0, 15500),
	("Lakeview Residency", "L2", "1", "Single Room", 1, 0, 15500),
	("Lakeview Residency", "L3", "2", "Double Sharing", 2, 0, 10000),
]
RENOVATION = {("Sunrise PG", "204")}

MEN = [
	"Aarav", "Rohan", "Karthik", "Vikram", "Arjun", "Siddharth", "Rahul", "Nikhil", "Pranav", "Aditya",
	"Varun", "Harsha", "Manoj", "Suresh", "Imran", "Joseph", "Deepak", "Akash", "Tejas", "Faisal",
]  # fmt: skip
WOMEN = [
	"Priya", "Ananya", "Sneha", "Divya", "Kavya", "Meera", "Pooja", "Shruti", "Nisha", "Fatima",
	"Lakshmi", "Riya", "Aishwarya", "Neha",
]  # fmt: skip
SURNAMES = [
	"Sharma", "Iyer", "Reddy", "Nair", "Gowda", "Patel", "Rao", "Menon", "Kulkarni", "Das", "Singh",
	"Khan", "Fernandes", "Hegde", "Joshi", "Pillai", "Shetty", "Verma", "Bhat", "Mukherjee",
]  # fmt: skip
WORK = [
	("Software Engineer", "Infosys, Electronic City", 85000),
	("Data Analyst", "Flipkart, Bellandur", 70000),
	("UX Designer", "Swiggy, Embassy Tech Village", 90000),
	("MBA Student", "Christ University", 0),
	("Staff Nurse", "Manipal Hospital, Old Airport Road", 42000),
	("Sales Executive", "Byju's, Bannerghatta Road", 38000),
	("QA Engineer", "Wipro, Sarjapur Road", 60000),
	("Chartered Accountant", "Deloitte, Koramangala", 95000),
	("Intern", "Razorpay, Koramangala", 25000),
	("Customer Support", "Amazon, Bellandur", 32000),
	("Backend Developer", "Zerodha, JP Nagar", 110000),
	("Lab Technician", "Narayana Health, Bommasandra", 30000),
]
HOMETOWNS = [
	"Mysuru, Karnataka", "Kochi, Kerala", "Hyderabad, Telangana", "Pune, Maharashtra",
	"Chennai, Tamil Nadu", "Lucknow, Uttar Pradesh", "Patna, Bihar", "Bhopal, Madhya Pradesh",
	"Mangaluru, Karnataka", "Vijayawada, Andhra Pradesh", "Kolkata, West Bengal", "Jaipur, Rajasthan",
]  # fmt: skip

# days ago, subject, category, priority, status, description, resolution
REQUESTS = [
	(1, "WiFi very slow on 2nd floor", "Internet / WiFi", "High", "Open",
		"Video calls keep dropping after 8 pm.", None),
	(3, "Geyser not heating", "Electrical", "High", "In Progress",
		"No hot water in the morning since yesterday.", "Electrician visiting tomorrow morning."),
	(6, "Tap leaking in bathroom", "Plumbing", "Medium", "Resolved",
		"The wash basin tap keeps dripping.", "Washer replaced by the plumber."),
	(11, "Cupboard lock broken", "Furniture", "Low", "Resolved",
		"The key turns but the lock doesn't open.", "New lock fitted, two keys given."),
	(18, "Too much noise after midnight", "Noise", "Medium", "Closed",
		"Music from the next room till 2 am on weekdays.", "Spoke to the residents about quiet hours."),
	(26, "Dinner served cold", "Food", "Low", "Closed",
		"Dinner is cold by 9 pm.", "Dinner is now kept in the hot case till 10 pm."),
	(2, "Room needs cleaning", "Cleaning", "Medium", "Open",
		"Housekeeping skipped our room this week.", None),
]  # fmt: skip


def make_demo_data(password: str = "demo@1234") -> dict:
	"""Fill an empty site with demo data. Returns a summary with the demo logins."""
	if frappe.db.count("Tenant") or frappe.db.count("Tenant Space"):
		frappe.throw(
			_(
				"This site already has rooms or tenants. Make the demo on a new site: "
				"bench new-site demo.localhost --install-app rent_management"
			)
		)
	return Demo(password).run()


class Demo:
	def __init__(self, password):
		self.password = password
		self.rng = random.Random(2026)
		self.today = getdate(nowdate())
		self.current_month = get_first_day(self.today)
		self.window_start = add_months(self.current_month, -(MONTHS_OF_HISTORY - 1))
		self.events, self.seq = [], 0
		self.people = self.make_people()

	def run(self) -> dict:
		settings = frappe.get_single(SETTINGS)
		send_receipts = settings.send_receipts
		settings.update({**LANDLORD, "send_receipts": 0})  # no receipts for the past
		settings.save()

		self.make_buildings()
		self.make_rooms()
		self.plan_stays()
		self.plan_events()
		while self.events:
			date, _order, _seq, action, payload = heapq.heappop(self.events)
			getattr(self, action)(date, payload)
		self.log_messages()
		logins = self.make_logins()

		frappe.db.set_single_value(SETTINGS, "send_receipts", send_receipts)
		frappe.clear_messages()
		return {
			"buildings": len(BUILDINGS),
			"rooms": len(ROOMS),
			"tenants": frappe.db.count("Tenant"),
			"invoices": frappe.db.count(INVOICE, {"docstatus": 1}),
			"payments": frappe.db.count("Rent Payment", {"docstatus": 1}),
			**logins,
		}

	# ------------------------------------------------------------ helpers

	def push(self, date, order, action, payload=None):
		self.seq += 1
		heapq.heappush(self.events, (getdate(date), order, self.seq, action, payload))

	def backdate(self, doctype, name, date):
		when = get_datetime(f"{getdate(date)} {self.rng.randint(9, 20):02d}:{self.rng.randint(0, 59):02d}:00")
		frappe.db.set_value(doctype, name, {"creation": when, "modified": when}, update_modified=False)

	def days_ago(self, days):
		return add_days(self.today, -days)

	def make_people(self) -> dict:
		people = {}
		for gender, first_names in (("Male", MEN), ("Female", WOMEN)):
			names = [(first, last) for first in first_names for last in SURNAMES]
			self.rng.shuffle(names)
			seen_first, unique, rest = set(), [], []
			for name in names:
				(rest if name[0] in seen_first else unique).append(name)
				seen_first.add(name[0])
			people[gender] = rest + unique  # pop() takes the unique first names first
		return people

	def aadhaar(self) -> str:
		digits = [self.rng.randint(2, 9)] + [self.rng.randint(0, 9) for _i in range(10)]
		return "".join(map(str, digits)) + verhoeff_digit(digits)

	# ------------------------------------------------------------ buildings and rooms

	def make_buildings(self):
		if frappe.db.exists("Rent Property", "Main Building") and not frappe.db.exists(
			"Tenant Space", {"property": "Main Building"}
		):
			frappe.delete_doc("Rent Property", "Main Building")  # the empty one made on install
		self.opened = {}
		for name, abbr, address, pincode, _for, opened in BUILDINGS:
			frappe.get_doc(
				{
					"doctype": "Rent Property",
					"property_name": name,
					"abbr": abbr,
					"address": address,
					"city": "Bengaluru",
					"state": "Karnataka",
					"pincode": pincode,
				}
			).insert()
			self.opened[name] = self.days_ago(opened)
		for room_type in ROOM_TYPES:
			if not frappe.db.exists("Tenant Space Type", room_type["type"]):
				frappe.get_doc(
					{"doctype": "Tenant Space Type", "deposit_applicable": 1, **room_type}
				).insert()

	def make_rooms(self):
		standard = {t["type"]: t["standard_rent"] for t in ROOM_TYPES}
		self.rooms = []
		for building, number, floor, room_type, beds, meter, rent in ROOMS:
			doc = frappe.get_doc(
				{
					"doctype": "Tenant Space",
					"property": building,
					"room_number": number,
					"floor": floor,
					"room_type": room_type,
					"capacity": beds,
					"room_rent": rent or standard[room_type],
					"has_meter": meter,
					"status": "Under Renovation" if (building, number) in RENOVATION else "Available",
				}
			).insert()
			self.rooms.append(frappe._dict(name=doc.name, building=building, beds=beds, meter=meter))

	# ------------------------------------------------------------ who stays where, when

	def plan_stays(self):
		rng, self.stays = self.rng, []
		for room in self.rooms:
			if frappe.db.get_value("Tenant Space", room.name, "status") == "Under Renovation":
				continue
			open_days = date_diff(self.today, self.opened[room.building])
			for bed in range(1, room.beds + 1):
				roll = rng.random()
				if roll < 0.25 and open_days > 300:
					# someone moved out in the last months; usually the bed was let again
					start, end = self.days_ago(rng.randint(240, 420)), self.days_ago(rng.randint(25, 140))
					self.stays.append(frappe._dict(room=room, bed=bed, start=start, end=end))
					if rng.random() < 0.7:
						self.stays.append(
							frappe._dict(room=room, bed=bed, start=add_days(end, rng.randint(4, 20)))
						)
				elif roll < 0.9:
					# most tenants stay long; a few moved in recently
					recent = rng.random() < 0.25 or open_days < 200
					days = rng.randint(12, min(180, open_days - 5)) if recent else rng.randint(200, 400)
					start = self.days_ago(days)
					self.stays.append(frappe._dict(room=room, bed=bed, start=start))

		current = [s for s in self.stays if not s.get("end")]
		for stay in self.stays:
			stay.behaviour = rng.choices(["on time", "late", "defaulter"], [70, 22, 8])[0]
			if stay.get("end"):
				stay.behaviour = "on time" if stay.behaviour == "defaulter" else stay.behaviour
			stay.deposit_collected = 1
			stay.parking = rng.random() < 0.12
			stay.rent_offer = 500 if rng.random() < 0.15 else 0  # negotiated at move-in

		long_stays = [s for s in current if s.start < add_days(self.window_start, -30)]
		self.notice_stay = long_stays[0]
		self.revised_stay = long_stays[1]
		self.app_tenant_stay = next(s for s in long_stays[2:] if s.room.building == BUILDINGS[0][0])
		self.app_tenant_stay.behaviour = "on time"
		# two tenants who are behind on rent, for the overdue lists and reminders
		others = [
			s for s in long_stays if s not in (self.notice_stay, self.revised_stay, self.app_tenant_stay)
		]
		for stay in current:
			if stay.behaviour == "defaulter":
				stay.behaviour = "late"
		for stay in rng.sample(others, 2):
			stay.behaviour = "defaulter"
		for stay in sorted(current, key=lambda s: s.start)[-2:]:
			stay.deposit_collected = 0  # just moved in, deposit not paid yet
		vacated = sorted((s for s in self.stays if s.get("end")), key=lambda s: s.end)
		self.unsettled_stay = vacated[-1] if vacated else None  # deposit still to settle
		self.adjusted_stay = vacated[-2] if len(vacated) > 1 else None  # deposit pays the last rent

	def plan_events(self):
		for stay in self.stays:
			self.push(stay.start, 1, "move_in", stay)
		month = self.window_start
		while month <= self.current_month:
			self.push(month, 2, "new_month", month)
			month = add_months(month, 1)
		self.push(self.days_ago(12), 5, "give_notice", self.notice_stay)
		for request in REQUESTS:
			self.push(self.days_ago(request[0]), 5, "raise_request", request)
		self.plan_expenses()

	def plan_expenses(self):
		rng = self.rng
		sun, villa, lake = (b[0] for b in BUILDINGS)
		month = self.window_start
		while month <= self.current_month:
			rows = [
				(sun, 1, "Salaries", 26000, "Warden and cook", "Bank Transfer"),
				(sun, 1, "Housekeeping & Cleaning", 5000, "Lakshmi (housekeeping)", "Cash"),
				(
					sun,
					3,
					"Food & Groceries",
					rng.randint(60, 80) * 100,
					"Metro Cash & Carry",
					"UPI",
				),
				(sun, 13, "Food & Groceries", rng.randint(60, 80) * 100, "Hopcoms", "UPI"),
				(
					sun,
					23,
					"Food & Groceries",
					rng.randint(60, 80) * 100,
					"Metro Cash & Carry",
					"UPI",
				),
				(sun, 5, "Internet & Cable", 2499, "ACT Fibernet", "UPI"),
				(sun, 8, "Electricity Bill", rng.randint(95, 125) * 100, "BESCOM", "UPI"),
				(sun, 15, "Water", 2500, "Water tanker", "Cash"),
				(
					villa,
					2,
					"Rent to Owner",
					30000,
					"Venkatesh Murthy (owner)",
					"Bank Transfer",
				),
				(villa, 1, "Salaries", 10000, "Caretaker", "Bank Transfer"),
				(villa, 1, "Housekeeping & Cleaning", 3500, "Cleaning staff", "Cash"),
				(villa, 5, "Internet & Cable", 1999, "Airtel Xstream", "UPI"),
				(villa, 9, "Electricity Bill", rng.randint(55, 75) * 100, "BESCOM", "UPI"),
				(lake, 1, "Salaries", 4000, "Part-time caretaker", "UPI"),
				(lake, 5, "Internet & Cable", 999, "ACT Fibernet", "UPI"),
				(lake, 9, "Electricity Bill", rng.randint(25, 35) * 100, "BESCOM", "UPI"),
			]
			for building in (sun, villa):
				if rng.random() < 0.6:
					what = rng.choice(["Plumber", "Electrician", "Carpenter", "Painting touch-up"])
					rows.append(
						(
							building,
							rng.randint(6, 26),
							"Repairs & Maintenance",
							rng.randint(8, 60) * 100,
							what,
							"Cash",
						)
					)
			for building, day, category, amount, paid_to, mode in rows:
				date = add_days(month, min(day, get_last_day(month).day) - 1)
				if date <= self.today and date >= self.opened[building]:
					self.push(date, 4, "add_expense", (building, category, amount, paid_to, mode))
			month = add_months(month, 1)
		opened = self.opened[lake]
		self.push(opened, 4, "add_expense", (lake, "Furniture & Equipment", 64000,
			"Beds, mattresses and cupboards", "Bank Transfer"))  # fmt: skip
		self.push(opened, 4, "add_expense", (lake, "Marketing", 2999, "NoBroker listing", "UPI"))

	# ------------------------------------------------------------ events

	def move_in(self, date, stay):
		gender = next(b[4] for b in BUILDINGS if b[0] == stay.room.building) or self.rng.choice(
			["Male", "Female"]
		)
		first, last = self.people[gender].pop()
		occupation, workspace, salary = self.rng.choice(WORK)
		tenant = frappe.get_doc(
			{
				"doctype": "Tenant",
				"first_name": first,
				"last_name": last,
				"gender": gender,
				"occupation": occupation,
				"workspace": workspace,
				"salary": salary,
				"mobile_no": f"{self.rng.choice('6789')}{self.rng.randint(100000000, 999999999)}",
				"email_id": f"{first}.{last}@example.com".lower(),
				"permanent_address": self.rng.choice(HOMETOWNS),
				"aadhar_card_number": self.aadhaar() if self.rng.random() < 0.75 else None,
			}
		).insert()
		self.backdate("Tenant", tenant.name, date)
		stay.tenant = tenant.name

		rent = frappe.db.get_value("Tenant Space", stay.room.name, "room_rent") - stay.rent_offer
		allotment = frappe.get_doc(
			{
				"doctype": ALLOTMENT,
				"tenant": tenant.name,
				"room": stay.room.name,
				"bed_no": stay.bed,
				"allotment_date": date,
				"rent_amount": rent,
				"deposit_collected": stay.deposit_collected,
				"deposit_collected_on": date if stay.deposit_collected else None,
			}
		).insert()
		allotment.submit()
		self.backdate(ALLOTMENT, allotment.name, date)
		stay.allotment = allotment.name
		if date >= self.window_start:
			self.make_invoice(stay, get_first_day(date), date)

	def new_month(self, month, _payload):
		self.read_meters(month)
		for stay in self.stays:
			if stay.get("end") and get_first_day(stay.end) == month:
				# they gave notice, so the last invoice is already only up to their move-out
				frappe.get_doc(ALLOTMENT, stay.allotment).vacate(stay.end)
				if stay is not self.unsettled_stay:
					settle_on = add_days(stay.end, self.rng.randint(2, 6))
					self.push(min(settle_on, self.today), 3, "settle_deposit", stay)
		if month == add_months(self.current_month, -2):
			frappe.get_doc(ALLOTMENT, self.revised_stay.allotment).revise_rent(
				frappe.db.get_value(ALLOTMENT, self.revised_stay.allotment, "rent_amount") + 500,
				month,
				"Moved to the bed by the window",
			)
		for stay in self.stays:
			if stay.get("allotment") and stay.start < month and not (stay.get("end") and stay.end < month):
				self.make_invoice(stay, month, month)

	def make_invoice(self, stay, month, posting_date):
		charges = []
		if stay.parking:
			charges.append({"charge_type": "Parking", "description": "Two-wheeler parking", "amount": 500})
		invoice = frappe.get_doc(
			{
				"doctype": INVOICE,
				"tenant_space_allotment": stay.allotment,
				"billing_month": MONTHS[month.month - 1],
				"billing_year": month.year,
				"posting_date": posting_date,
				"charges": charges,
			}
		).insert()
		invoice.submit()
		self.backdate(INVOICE, invoice.name, posting_date)
		self.plan_payments(stay, invoice, month)

	def plan_payments(self, stay, invoice, month):
		months_ago = (self.current_month.year - month.year) * 12 + self.current_month.month - month.month
		is_last = stay.get("end") and get_first_day(stay.end) == month
		if is_last and stay is self.adjusted_stay:
			return  # paid from the deposit
		if stay is self.app_tenant_stay and months_ago == 0:
			return  # due now: shows "Pay now" in the tenant app
		if stay.behaviour == "defaulter" and months_ago <= 1:
			if months_ago == 1:
				partly = round(flt(invoice.final_amount) * 0.4, -2)
				self.push(add_days(invoice.due_date, 9), 3, "pay", (invoice.name, partly))
			return
		offset = self.rng.randint(6, 16) if stay.behaviour == "late" else self.rng.randint(0, 4)
		date = add_days(max(getdate(invoice.posting_date), month), offset)
		if date <= self.today:
			self.push(date, 3, "pay", (invoice.name, None))

	def pay(self, date, payload):
		invoice, amount = payload
		outstanding = flt(frappe.db.get_value(INVOICE, invoice, "outstanding_amount"))
		if outstanding <= 0:
			return
		mode = self.rng.choices(["UPI", "Cash", "Bank Transfer"], [70, 15, 15])[0]
		payment = frappe.get_doc(
			{
				"doctype": "Rent Payment",
				"tenant": frappe.db.get_value(INVOICE, invoice, "tenant"),
				"rent_invoice": invoice,
				"amount": min(amount or outstanding, outstanding),
				"mode_of_payment": mode,
				"payment_date": date,
				"reference_no": str(self.rng.randint(10**11, 10**12 - 1)) if mode != "Cash" else None,
			}
		).insert()
		payment.submit()
		self.backdate("Rent Payment", payment.name, date)

	def read_meters(self, month):
		if not hasattr(self, "meters"):
			self.meters = {}
		previous = add_months(month, -1)
		for room in self.rooms:
			if (
				not room.meter
				or frappe.db.get_value("Tenant Space", room.name, "status") == "Under Renovation"
			):
				continue
			if room.name not in self.meters:
				self.meters[room.name] = self.rng.randint(1200, 8000)  # opening reading
			else:
				days = sum(self.days_in_room(stay, previous, add_days(month, -1)) for stay in self.stays
					if stay.room is room)  # fmt: skip
				self.meters[room.name] += round(days * self.rng.uniform(3.0, 4.5) + 15, 1)
			reading = frappe.get_doc(
				{
					"doctype": "Meter Reading",
					"room": room.name,
					"reading_date": month,
					"reading": self.meters[room.name],
				}
			).insert()
			self.backdate("Meter Reading", reading.name, month)

	@staticmethod
	def days_in_room(stay, start, end) -> int:
		first, last = max(getdate(stay.start), start), min(getdate(stay.get("end") or end), end)
		return max(date_diff(last, first) + 1, 0)

	def settle_deposit(self, date, stay):
		from rent_management.api import make_settlement

		deductions = [{"reason": "Cleaning", "description": "Deep cleaning after move-out", "amount": 500}]
		if self.rng.random() < 0.4:
			deductions.append({"reason": "Damages", "description": "Broken chair", "amount": 1200})
		settlement = make_settlement(
			stay.allotment,
			deductions=deductions,
			adjust_outstanding_rent=1,
			settlement_date=date,
			mode_of_refund="UPI",
		).insert()
		settlement.submit()
		self.backdate("Security Deposit Settlement", settlement.name, date)

	def give_notice(self, date, stay):
		frappe.get_doc(ALLOTMENT, stay.allotment).give_notice(date)

	def raise_request(self, date, request):
		_days, subject, category, priority, status, description, resolution = request
		stay = self.rng.choice([s for s in self.stays if not s.get("end") and s.start < date])
		if subject.startswith("Dinner") or subject.startswith("WiFi"):
			stay = self.app_tenant_stay  # so the tenant app has requests to show
		doc = frappe.get_doc(
			{
				"doctype": "Maintenance Request",
				"subject": subject,
				"category": category,
				"priority": priority,
				"status": status,
				"tenant": stay.tenant,
				"description": description,
				"resolution": resolution,
				"resolved_on": get_datetime(f"{add_days(date, 1)} 11:30:00")
				if status in ("Resolved", "Closed")
				else None,
				"raised_via": "Tenant App" if self.rng.random() < 0.7 else "Manager",
			}
		).insert()
		self.backdate("Maintenance Request", doc.name, date)

	def add_expense(self, date, payload):
		building, category, amount, paid_to, mode = payload
		doc = frappe.get_doc(
			{
				"doctype": "Property Expense",
				"property": building,
				"expense_date": date,
				"category": category,
				"amount": amount,
				"paid_to": paid_to,
				"mode_of_payment": mode,
			}
		).insert()
		self.backdate("Property Expense", doc.name, date)

	# ------------------------------------------------------------ messages and logins

	def log_messages(self):
		"""What the reminders and receipts of the last days would have sent."""
		since = self.days_ago(10)
		for payment in frappe.get_all(
			"Rent Payment",
			filters={
				"docstatus": 1,
				"payment_date": (">=", since),
				"mode_of_payment": ("!=", "Security Deposit"),
			},
			fields=["name", "tenant", "tenant_name", "rent_invoice", "amount", "payment_date"],
		):
			self.log("Receipt", payment, payment.payment_date, rent_payment=payment.name,
				message=f"Hello {payment.tenant_name}, we have received ₹{payment.amount:,.0f}. Thank you!")  # fmt: skip
		for invoice in frappe.get_all(
			INVOICE,
			filters={"docstatus": 1, "status": "Overdue"},
			fields=["name", "tenant", "tenant_name", "outstanding_amount", "due_date"],
		):
			self.log("Overdue", invoice, min(add_days(invoice.due_date, 3), self.today),
				message=f"Hello {invoice.tenant_name}, your rent of ₹{invoice.outstanding_amount:,.0f} is still unpaid.")  # fmt: skip

	def log(self, message_type, row, date, message, rent_payment=None):
		doc = frappe.get_doc(
			{
				"doctype": "Rent Message Log",
				"message_type": message_type,
				"channel": "WhatsApp",
				"status": "Sent",
				"recipient": frappe.db.get_value("Tenant", row.tenant, "mobile_no"),
				"tenant": row.tenant,
				"tenant_name": row.tenant_name,
				"rent_invoice": row.get("rent_invoice") or row.name,
				"rent_payment": rent_payment,
				"message": message,
			}
		).insert(ignore_permissions=True)
		self.backdate("Rent Message Log", doc.name, date)

	def make_logins(self) -> dict:
		from rent_management.portal import TENANT_ROLE, ensure_tenant_role

		manager = "manager@example.com"
		if not frappe.db.exists("User", manager):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": manager,
					"first_name": "Ravi",
					"last_name": "Kumar",
					"send_welcome_email": 0,
					"roles": [{"role": "Rent Manager"}],
				}
			).insert(ignore_permissions=True)
		update_password(manager, self.password)

		ensure_tenant_role()
		tenant = frappe.get_doc("Tenant", self.app_tenant_stay.tenant)
		if not frappe.db.exists("User", tenant.email_id):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": tenant.email_id,
					"first_name": tenant.first_name,
					"last_name": tenant.last_name,
					"user_type": "Website User",
					"send_welcome_email": 0,
					"roles": [{"role": TENANT_ROLE}],
				}
			).insert(ignore_permissions=True)
		update_password(tenant.email_id, self.password)
		tenant.db_set("user", tenant.email_id)
		return {"manager_login": manager, "tenant_login": tenant.email_id, "password": self.password}


VERHOEFF_D = [
	[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
	[1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
	[2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
	[3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
	[4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
	[5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
	[6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
	[7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
	[8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
	[9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
VERHOEFF_P = [
	[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
	[1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
	[5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
	[8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
	[9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
	[4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
	[2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
	[7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_digit(digits) -> str:
	"""The check digit that makes a (demo) Aadhaar number pass validation."""
	c = 0
	for i, digit in enumerate(reversed(digits)):
		c = VERHOEFF_D[c][VERHOEFF_P[(i + 1) % 8][digit]]
	return str(VERHOEFF_INV[c])
