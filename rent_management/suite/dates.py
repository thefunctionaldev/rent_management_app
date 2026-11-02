"""Pure calendar helpers shared by bills and housekeeping."""

from calendar import monthrange
from datetime import date, timedelta


def next_occurrence(current, frequency, anchor):
	current = date.fromisoformat(str(current)[:10])
	anchor = date.fromisoformat(str(anchor)[:10])
	if frequency in ("Daily", "Weekly"):
		return current + timedelta(days=1 if frequency == "Daily" else 7)
	months = {"Monthly": 1, "Quarterly": 3, "Yearly": 12}[frequency]
	serial = current.year * 12 + current.month - 1 + months
	year, month = serial // 12, serial % 12 + 1
	return date(year, month, min(anchor.day, monthrange(year, month)[1]))


def can_transition(current, action):
	return current in {
		"request": {"Draft"},
		"approve": {"Pending Approval"},
		"reject": {"Pending Approval"},
		"start": {"Approved"},
		"complete": {"In Progress"},
		"confirm": {"Completed"},
		"cancel": {"Draft", "Pending Approval", "Approved"},
	}.get(action, set())
