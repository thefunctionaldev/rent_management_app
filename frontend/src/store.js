import { reactive } from "vue";

import { get } from "./api";

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
});

export async function loadBoot() {
	Object.assign(boot, await get("get_boot"), { loaded: true });
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
