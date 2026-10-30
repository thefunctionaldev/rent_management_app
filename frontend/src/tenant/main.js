import { createApp } from "vue";

import "../style.css";
import { setupPwa } from "@/pwa";

import App from "./App.vue";
import router from "./router";
import { loadMe } from "./store";

setupPwa("tenant");
loadMe()
	.catch(() => {
		window.location.href = `/login?redirect-to=${encodeURIComponent(
			window.location.pathname
		)}`;
	})
	.finally(() => createApp(App).use(router).mount("#app"));
