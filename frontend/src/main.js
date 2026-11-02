import { i18n, loadLanguage } from "@/i18n";
import { createApp } from "vue";

import App from "./App.vue";
import { setupPwa } from "./pwa";
import router from "./router";
import { loadBoot } from "./store";
import "./style.css";

setupPwa("rent");
Promise.all([loadBoot(), loadLanguage()])
	.catch(() => {
		// not logged in, or no access: send to the login page
		window.location.href = `/login?redirect-to=${encodeURIComponent(window.location.pathname)}`;
	})
	.finally(() => createApp(App).use(i18n).use(router).mount("#app"));
