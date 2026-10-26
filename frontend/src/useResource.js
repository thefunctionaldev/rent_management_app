import { ref, watch } from "vue";

import { bumpData, dataVersion, toast, ui } from "./store";

// Loads data from an async function and reloads whenever dialogs change data.
export function useResource(fetcher, { immediate = true, initial = null } = {}) {
	const data = ref(initial);
	const loading = ref(false);
	const error = ref(null);

	async function reload() {
		loading.value = true;
		error.value = null;
		try {
			data.value = await fetcher();
		} catch (e) {
			error.value = e.message;
			toast(e.message, "error");
		} finally {
			loading.value = false;
		}
	}

	// reload after dialogs change data, and when the building switcher changes
	watch([() => dataVersion.value, () => ui.property], reload);
	if (immediate) reload();
	return { data, loading, error, reload };
}

// Runs a write call with a loading flag, shows a toast and refreshes pages on success.
export function useAction(fn, { success } = {}) {
	const loading = ref(false);

	async function run(...args) {
		loading.value = true;
		try {
			const result = await fn(...args);
			if (success) toast(typeof success === "function" ? success(result) : success);
			bumpData();
			return result;
		} catch (e) {
			toast(e.message, "error");
			throw e;
		} finally {
			loading.value = false;
		}
	}

	return { loading, run };
}
