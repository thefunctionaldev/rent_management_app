import { createApp } from "vue";
import App from "./App.vue";
import { i18n, loadLanguage } from "@/i18n";
import "@/style.css";
loadLanguage().finally(() => createApp(App).use(i18n).mount("#app"));
