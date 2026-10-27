import { createApp } from "vue";

import "../style.css";
import { boot } from "../store";
import Checkin from "./Checkin.vue";

boot.currency = "INR";
createApp(Checkin).mount("#app");
