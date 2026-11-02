import { i18n, loadLanguage } from "@/i18n";
import { createApp } from "vue";

import "../style.css";
import { setupPwa } from "@/pwa";

import App from "./App.vue";
import router from "./router";
import { loadMe } from "./store";

setupPwa("tenant");
Promise.all([loadMe(), loadLanguage()])
	.catch(() => {
		window.location.href = `/login?redirect-to=${encodeURIComponent(
			window.location.pathname
		)}`;
	})
	.finally(() => createApp(App).use(i18n).use(router).mount("#app"));
