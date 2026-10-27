import { createApp } from "vue";

import "../style.css";
import { boot } from "../store";
import Stay from "./Stay.vue";

boot.currency = "INR"; // money() formats in rupees
createApp(Stay).mount("#app");
