import { boot } from "./store";

const locale = () => (boot.currency === "INR" ? "en-IN" : undefined);

export function money(value, { compact = false, currency } = {}) {
	const amount = Number(value || 0);
	return new Intl.NumberFormat(locale(), {
		style: "currency",
		currency: currency || boot.currency || "INR",
		notation: compact ? "compact" : "standard",
		// whole amounts without decimals, anything with paise always as .xx
		maximumFractionDigits: compact ? 1 : amount % 1 ? 2 : 0,
		minimumFractionDigits: !compact && amount % 1 ? 2 : 0,
	}).format(amount);
}

export function date(value, options = { day: "numeric", month: "short", year: "numeric" }) {
	if (!value) return "—";
	return new Intl.DateTimeFormat(locale(), options).format(new Date(`${value}T00:00:00`));
}

export function shortDate(value) {
	return date(value, { day: "numeric", month: "short" });
}

export function daysBetween(from, to = boot.today) {
	if (!from) return 0;
	return Math.round((new Date(`${to}T00:00:00`) - new Date(`${from}T00:00:00`)) / 86400000);
}

export function initials(name = "") {
	return (
		name
			.split(" ")
			.filter(Boolean)
			.slice(0, 2)
			.map((part) => part[0].toUpperCase())
			.join("") || "?"
	);
}

export function currentMonth() {
	const today = new Date(`${boot.today}T00:00:00`);
	return { month: boot.months[today.getMonth()], year: today.getFullYear() };
}

export function whatsappReminder(mobile, invoice) {
	if (!mobile) return null;
	const digits = mobile.replace(/[^\d]/g, "");
	const text =
		`Hello ${invoice.tenant_name}, this is a reminder that rent of ${money(
			invoice.outstanding_amount
		)} ` +
		`for ${invoice.billing_month} ${invoice.billing_year} (room ${invoice.room}) is due` +
		(invoice.due_date ? ` on ${date(invoice.due_date)}` : "") +
		". Thank you!";
	return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}

export function debounce(fn, wait = 300) {
	let timer;
	return (...args) => {
		clearTimeout(timer);
		timer = setTimeout(() => fn(...args), wait);
	};
}
