import { createApp } from "vue";

import "../style.css";
import App from "./App.vue";
import router from "./router";
import { loadMe } from "./store";

loadMe()
	.catch(() => {
		window.location.href = `/login?redirect-to=${encodeURIComponent(
			window.location.pathname
		)}`;
	})
	.finally(() => createApp(App).use(router).mount("#app"));
