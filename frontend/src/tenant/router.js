import { createRouter, createWebHistory } from "vue-router";

const routes = [
	{ path: "/", name: "home", component: () => import("./pages/Home.vue") },
	{ path: "/invoices", name: "bills", component: () => import("./pages/Bills.vue") },
	{
		path: "/invoices/:name",
		name: "bill",
		component: () => import("./pages/Bill.vue"),
		props: true,
	},
	{ path: "/requests", name: "requests", component: () => import("./pages/Requests.vue") },
	{ path: "/food", name: "food", component: () => import("./pages/Food.vue") },
	{ path: "/away", name: "away", component: () => import("./pages/Register.vue") },
	{ path: "/refer", name: "refer", component: () => import("./pages/Refer.vue") },
	{ path: "/notices", name: "notices", component: () => import("./pages/Notices.vue") },
	{ path: "/receipts", name: "receipts", component: () => import("./pages/Receipts.vue") },
	{ path: "/profile", name: "profile", component: () => import("./pages/Profile.vue") },
	{ path: "/:pathMatch(.*)*", redirect: "/" },
];

export default createRouter({
	history: createWebHistory("/tenant/"),
	routes,
	scrollBehavior: () => ({ top: 0 }),
});
