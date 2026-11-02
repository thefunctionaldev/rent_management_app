// ISO calendar dates are compared as dates, without browser timezone conversions.
export function addDate(day, offset) {
	if (!/^\d{4}-\d{2}-\d{2}$/.test(day || "")) return "";
	const value = new Date(`${day}T12:00:00Z`);
	value.setUTCDate(value.getUTCDate() + offset);
	return value.toISOString().slice(0, 10);
}
export function occupancyCell(bed, day, stays) {
	const matches = stays.filter(
		(s) =>
			s.allotment_date <= day &&
			(s.status === "Active" ||
				(s.status === "Vacated" && (!s.vacate_date || s.vacate_date >= day)))
	);
	if (matches.length > 1)
		return { label: "Conflict — review stays", tone: "bg-rose-100 text-rose-800" };
	const stay = matches[0];
	if (stay)
		return {
			label: stay.tenant_name || "Occupied",
			tenant: stay.tenant,
			notice: stay.expected_vacate_date === day,
			tone:
				stay.expected_vacate_date === day
					? "bg-amber-100 text-amber-900"
					: "bg-brand-50 text-brand-800",
		};
	if (["Under Renovation", "Reserved"].includes(bed.room.status))
		return { label: bed.room.status, tone: "bg-slate-200 text-slate-700" };
	return { label: "Unallotted", tone: "bg-emerald-50 text-emerald-800" };
}
