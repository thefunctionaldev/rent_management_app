# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Food: meal plans, the weekly menu, skipped meals and what the kitchen cooks.

A building with Food Included serves some of breakfast, lunch and dinner. Each stay has a
meal plan: none, included in the rent, or paid monthly (added to every rent invoice for
the days stayed). Tenants skip meals from the tenant app until a cutoff before the meal,
so the kitchen knows how many to cook; the food cost per meal comes from the building's
Food & Groceries expenses divided by the meals actually served.
"""

from collections import defaultdict
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	date_diff,
	flt,
	get_first_day,
	get_last_day,
	get_time,
	getdate,
	now_datetime,
	nowdate,
)

MEALS = ("Breakfast", "Lunch", "Dinner")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
OPTOUT = "Meal Opt-out"
FOOD_CATEGORY = "Food & Groceries"


def meals_of(building) -> list[dict]:
	"""The meals a building serves, with their times."""
	doc = frappe.get_cached_doc("Rent Property", building) if isinstance(building, str) else building
	if not cint(doc.food_included):
		return []
	return [
		{"meal": meal, "time": get_time(doc.get(f"{meal.lower()}_time") or "12:00:00").strftime("%H:%M")}
		for meal in MEALS
		if cint(doc.get(f"serves_{meal.lower()}"))
	]


def meal_at(building, day, meal) -> datetime:
	doc = frappe.get_cached_doc("Rent Property", building)
	return datetime.combine(getdate(day), get_time(doc.get(f"{meal.lower()}_time") or "12:00:00"))


def cutoff(building, day, meal) -> datetime:
	hours = cint(frappe.get_cached_doc("Rent Property", building).meal_skip_cutoff_hours)
	return meal_at(building, day, meal) - timedelta(hours=hours)


def stays_eating(building, day) -> list[frappe._dict]:
	"""Stays with a meal plan in the building on that day."""
	day = getdate(day)
	return frappe.get_all(
		"Tenant Space Allotment",
		filters={
			"docstatus": 1,
			"property": building,
			"meal_plan": ("is", "set"),
			"allotment_date": ("<=", day),
			"status": ("in", ("Active", "Vacated")),
		},
		or_filters=[["vacate_date", "is", "not set"], ["vacate_date", ">=", day]],
		fields=["name", "tenant", "tenant_name", "room"],
	)


def kitchen_count(building, day) -> list[dict]:
	"""For each meal of the day: how many eat, and who is skipping."""
	stays = stays_eating(building, day)
	names = {s.name: s for s in stays}
	skipped = defaultdict(list)
	for row in frappe.get_all(
		OPTOUT, filters={"property": building, "date": getdate(day)}, fields=["allotment", "meal"]
	):
		if row.allotment in names:
			skipped[row.meal].append(names[row.allotment])
	return [
		{
			**meal,
			"expected": len(stays),
			"eating": len(stays) - len(skipped[meal["meal"]]),
			"skipping": [{"tenant_name": s.tenant_name, "room": s.room} for s in skipped[meal["meal"]]],
		}
		for meal in meals_of(building)
	]


def meals_served(building, start, end) -> int:
	"""Meals actually eaten in a period (everyone with a plan, less skipped meals)."""
	served, day = 0, getdate(start)
	meals = len(meals_of(building))
	if not meals:
		return 0
	while day <= getdate(end):
		served += len(stays_eating(building, day)) * meals
		day = add_days(day, 1)
	return served - frappe.db.count(OPTOUT, {"property": building, "date": ("between", (start, end))})


def food_costs(building, month_start) -> dict:
	month_start = get_first_day(month_start)
	end = min(get_last_day(month_start), getdate(nowdate()))
	spent = flt(
		frappe.db.sql(
			"""select sum(amount) from `tabProperty Expense`
			where property=%s and category=%s and expense_date between %s and %s""",
			(building, FOOD_CATEGORY, month_start, end),
		)[0][0]
	)
	served = meals_served(building, month_start, end)
	days = date_diff(end, month_start) + 1
	eaters = len(stays_eating(building, end))
	return {
		"month": month_start.strftime("%B %Y"),
		"spent": spent,
		"meals_served": served,
		"per_meal": flt(spent / served, 2) if served else 0,
		"per_tenant_month": flt(spent / days * 30 / eaters, 0) if eaters and days else 0,
		"skipped": frappe.db.count(OPTOUT, {"property": building, "date": ("between", (month_start, end))}),
	}


# ---------------------------------------------------------------- menu


def get_menu(building) -> dict:
	rows = (
		frappe.get_all(
			"Mess Menu Item",
			filters={"parent": building, "parenttype": "Mess Menu"},
			fields=["day", "meal", "dishes"],
		)
		if frappe.db.exists("Mess Menu", building)
		else []
	)
	menu = {day: {meal: "" for meal in MEALS} for day in DAYS}
	for row in rows:
		menu[row.day][row.meal] = row.dishes or ""
	return menu


def save_menu(building, menu):
	menu = frappe.parse_json(menu) or {}
	doc = (
		frappe.get_doc("Mess Menu", building)
		if frappe.db.exists("Mess Menu", building)
		else frappe.new_doc("Mess Menu")
	)
	doc.property = building
	doc.set(
		"items",
		[
			{"day": day, "meal": meal, "dishes": (menu.get(day) or {}).get(meal, "").strip()}
			for day in DAYS
			for meal in MEALS
			if ((menu.get(day) or {}).get(meal) or "").strip()
		],
	)
	doc.save()


def menu_for(building, day) -> dict:
	return get_menu(building)[DAYS[getdate(day).weekday()]]


# ---------------------------------------------------------------- skipping meals


def set_skip(allotment, day, meal, skip, source="Tenant App"):
	stay = frappe.get_doc("Tenant Space Allotment", allotment)
	if not stay.meal_plan:
		frappe.throw(_("There's no meal plan for this stay."))
	if meal not in [m["meal"] for m in meals_of(stay.property)]:
		frappe.throw(_("{0} isn't served here.").format(meal))
	if source == "Tenant App" and now_datetime() > cutoff(stay.property, day, meal):
		frappe.throw(
			_("It's too late to change {0} on {1}.").format(_(meal).lower(), frappe.utils.formatdate(day))
		)
	existing = frappe.db.get_value(OPTOUT, {"allotment": allotment, "date": getdate(day), "meal": meal})
	if skip and not existing:
		doc = frappe.get_doc(
			{"doctype": OPTOUT, "allotment": allotment, "date": getdate(day), "meal": meal, "source": source}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
	elif not skip and existing:
		frappe.delete_doc(OPTOUT, existing, ignore_permissions=True)


def tenant_week(stay, days=7) -> dict:
	"""The tenant app's Food page: the next days' meals, menu and whether they eat."""
	meals = meals_of(stay.property)
	skipped = {
		(str(r.date), r.meal)
		for r in frappe.get_all(
			OPTOUT,
			filters={"allotment": stay.name, "date": (">=", nowdate())},
			fields=["date", "meal"],
		)
	}
	menu = get_menu(stay.property)
	now = now_datetime()
	result = []
	for offset in range(days):
		day = add_days(getdate(nowdate()), offset)
		rows = []
		for meal in meals:
			at = meal_at(stay.property, day, meal["meal"])
			if at < now:
				continue  # already served
			rows.append(
				{
					**meal,
					"dishes": menu[DAYS[day.weekday()]][meal["meal"]],
					"eating": (str(day), meal["meal"]) not in skipped,
					"can_change": now <= cutoff(stay.property, day, meal["meal"]),
					"cutoff": str(cutoff(stay.property, day, meal["meal"])),
				}
			)
		if rows:
			result.append({"date": str(day), "day": DAYS[day.weekday()], "meals": rows})
	return {
		"plan": stay.meal_plan,
		"days": result,
		"cutoff_hours": frappe.get_cached_doc("Rent Property", stay.property).meal_skip_cutoff_hours,
	}


# ---------------------------------------------------------------- billing


def add_meal_charges(invoice):
	"""A Paid Monthly meal plan, for the days of the month the tenant stays."""
	stay = frappe.db.get_value(
		"Tenant Space Allotment",
		invoice.tenant_space_allotment,
		["meal_plan", "meal_charge", "allotment_date", "vacate_date"],
		as_dict=True,
	)
	if not stay or stay.meal_plan != "Paid Monthly" or not flt(stay.meal_charge):
		return
	if any(row.charge_type == "Food" for row in invoice.charges):
		return
	from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS

	start = getdate(f"{invoice.billing_year}-{MONTHS.index(invoice.billing_month) + 1:02d}-01")
	end = get_last_day(start)
	first = max(start, getdate(stay.allotment_date))
	last = min(end, getdate(stay.vacate_date)) if stay.vacate_date else end
	days = date_diff(last, first) + 1
	if days <= 0:
		return
	total = date_diff(end, start) + 1
	amount = flt(flt(stay.meal_charge) * days / total, 2)
	invoice.append(
		"charges",
		{
			"charge_type": "Food",
			"description": _("Meals, {0} days").format(days) if days < total else _("Meals"),
			"amount": amount,
		},
	)
