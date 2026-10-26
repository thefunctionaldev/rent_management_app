import { createRouter, createWebHistory } from "vue-router";

const routes = [
	{ path: "/", name: "dashboard", component: () => import("./pages/Dashboard.vue") },
	{ path: "/rooms", name: "rooms", component: () => import("./pages/Rooms.vue") },
	{ path: "/tenants", name: "tenants", component: () => import("./pages/Tenants.vue") },
	{
		path: "/tenants/:name",
		name: "tenant",
		component: () => import("./pages/TenantDetail.vue"),
		props: true,
	},
	{ path: "/invoices", name: "invoices", component: () => import("./pages/Invoices.vue") },
	{ path: "/payments", name: "payments", component: () => import("./pages/Payments.vue") },
	{ path: "/deposits", name: "deposits", component: () => import("./pages/Deposits.vue") },
	{
		path: "/outstanding",
		name: "outstanding",
		component: () => import("./pages/Outstanding.vue"),
	},
	{ path: "/billing", name: "billing", component: () => import("./pages/Billing.vue") },
	{ path: "/:pathMatch(.*)*", redirect: "/" },
];

export default createRouter({
	history: createWebHistory("/rent/"),
	routes,
	scrollBehavior: () => ({ top: 0 }),
});
