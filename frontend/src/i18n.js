import { ref } from "vue";
import { get, post } from "./api";
import hi from "./locales/hi.json";
export const language = ref("en");
export function t(value) {
	return language.value === "hi" ? hi[value] || value : value;
}
function apply(value) {
	language.value = value === "hi" ? "hi" : "en";
	document.documentElement.lang = language.value;
}
export async function loadLanguage() {
	try {
		apply(await get("rent_management.suite.language.preference"));
	} catch {
		apply("en");
	}
}
export async function setLanguage(value) {
	apply(await post("rent_management.suite.language.set_preference", { language: value }));
}
export const i18n = {
	install(app) {
		app.config.globalProperties.$t = t;
	},
};
