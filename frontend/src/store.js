import { reactive } from "vue";

import { get, setFixedArgs } from "./api";

export const boot = reactive({
	loaded: false,
	user: "",
	full_name: "",
	user_image: null,
	currency: "INR",
	currency_symbol: "₹",
	months: [],
	today: new Date().toISOString().slice(0, 10),
	subscription: null,
	properties: [],
});

// --- building switcher ---------------------------------------------------------

const PROPERTY_KEY = "rent:property";
function storedProperty() {
	try {
		return localStorage.getItem(PROPERTY_KEY) || "";
	} catch {
		return "";
	}
}

// the building every list is narrowed to ("" = all buildings)
export const ui = reactive({ property: storedProperty() });

export function setProperty(property) {
	ui.property = property || "";
	try {
		localStorage.setItem(PROPERTY_KEY, ui.property);
	} catch {
		// private mode: the choice just isn't remembered
	}
}

// spread into API args of lists that can be narrowed to a building
export const scope = () => (ui.property ? { property: ui.property } : {});

export const activeProperties = () => boot.properties.filter((p) => p.is_active);

export async function loadBoot() {
	Object.assign(boot, await get("get_boot"), { loaded: true });
	if (boot.access?.building) {
		// a staff login for one building: always that building
		ui.property = boot.access.building;
		setFixedArgs({ property: boot.access.building });
	} else if (ui.property && !boot.properties.some((p) => p.name === ui.property))
		setProperty("");
}

// staff logins can use only their areas (rent_management/access.py); managers everything.
// `areas` is one area or a list (any of them will do); none means managers only.
export function canUse(areas) {
	if (!boot.access) return true;
	if (!areas) return false;
	return [].concat(areas).some((a) => boot.access.areas.includes(a));
}

export async function reloadProperties() {
	boot.properties = await get("get_properties");
}

// --- toasts ---------------------------------------------------------------

export const toasts = reactive([]);
let toastId = 0;

export function toast(message, type = "success") {
	const id = ++toastId;
	toasts.push({ id, message, type });
	setTimeout(() => dismissToast(id), type === "error" ? 6000 : 3500);
}

export function dismissToast(id) {
	const index = toasts.findIndex((t) => t.id === id);
	if (index !== -1) toasts.splice(index, 1);
}

// --- cross-page refresh ------------------------------------------------------

// pages watch this to reload after a dialog changes data
export const dataVersion = reactive({ value: 0 });
export const bumpData = () => dataVersion.value++;
