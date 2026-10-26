import { reactive } from "vue";

import { get } from "@/api";
import { boot } from "@/store";

const METHOD = "rent_management.portal.";
export const call = (method) => METHOD + method;

export const me = reactive({ loaded: false });

export async function loadMe() {
	Object.assign(me, await get(call("get_boot")), { loaded: true });
	// shared helpers (money, dates) read these
	Object.assign(boot, {
		currency: me.currency,
		currency_symbol: me.currency_symbol,
		today: me.today,
	});
}
