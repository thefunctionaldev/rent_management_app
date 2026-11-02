import { i18n } from "@/i18n";
import { createApp } from "vue";

import "../style.css";
import { boot } from "../store";
import Checkin from "./Checkin.vue";

boot.currency = "INR";
createApp(Checkin).use(i18n).mount("#app");
