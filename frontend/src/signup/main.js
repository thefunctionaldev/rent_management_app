import { i18n } from "@/i18n";
import { createApp } from "vue";

import "../style.css";
import Signup from "./Signup.vue";

createApp(Signup).use(i18n).mount("#app");
