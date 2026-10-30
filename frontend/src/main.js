import { createApp } from "vue";

import App from "./App.vue";
import { setupPwa } from "./pwa";
import router from "./router";
import { loadBoot } from "./store";
import "./style.css";

setupPwa("rent");
loadBoot()
	.catch(() => {
		// not logged in, or no access: send to the login page
		window.location.href = `/login?redirect-to=${encodeURIComponent(
			window.location.pathname
		)}`;
	})
	.finally(() => createApp(App).use(router).mount("#app"));
