import { i18n } from "@/i18n";
import { createApp } from "vue";

import "../style.css";
import { boot } from "../store";
import Stay from "./Stay.vue";

boot.currency = "INR"; // money() formats in rupees
createApp(Stay).use(i18n).mount("#app");
