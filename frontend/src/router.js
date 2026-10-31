import { createRouter, createWebHistory } from "vue-router";

import { boot, canUse } from "./store";

const routes = [
	// managers see the dashboard, staff logins their own home page
	{
		path: "/",
		name: "dashboard",
		meta: { everyone: true },
		component: () => import("./pages/Home.vue"),
	},
	{
		path: "/rooms",
		meta: { area: ["rooms", "leads"] },
		name: "rooms",
		component: () => import("./pages/Rooms.vue"),
	},
	{
		path: "/tenants",
		meta: { area: ["rooms", "payments"] },
		name: "tenants",
		component: () => import("./pages/Tenants.vue"),
	},
	{
		path: "/tenants/:name",
		meta: { area: ["rooms", "payments"] },
		name: "tenant",
		component: () => import("./pages/TenantDetail.vue"),
		props: true,
	},
	{
		path: "/invoices",
		meta: { area: "payments" },
		name: "invoices",
		component: () => import("./pages/Invoices.vue"),
	},
	{
		path: "/payments",
		meta: { area: "payments" },
		name: "payments",
		component: () => import("./pages/Payments.vue"),
	},
	{ path: "/deposits", name: "deposits", component: () => import("./pages/Deposits.vue") },
	{
		path: "/outstanding",
		meta: { area: "payments" },
		name: "outstanding",
		component: () => import("./pages/Outstanding.vue"),
	},
	{ path: "/buildings", name: "buildings", component: () => import("./pages/Buildings.vue") },
	{ path: "/import", name: "import", component: () => import("./pages/Import.vue") },
	{ path: "/settings", name: "settings", component: () => import("./pages/Settings.vue") },
	{
		path: "/electricity",
		meta: { area: "meters" },
		name: "electricity",
		component: () => import("./pages/Electricity.vue"),
	},
	{
		path: "/expenses",
		meta: { area: "expenses" },
		name: "expenses",
		component: () => import("./pages/Expenses.vue"),
	},
	{ path: "/profit", name: "profit", component: () => import("./pages/Profit.vue") },
	{
		path: "/requests",
		meta: { area: "requests" },
		name: "requests",
		component: () => import("./pages/Requests.vue"),
	},
	{
		path: "/leads",
		meta: { area: "leads" },
		name: "leads",
		component: () => import("./pages/Leads.vue"),
	},
	{
		path: "/food",
		meta: { area: "food" },
		name: "food",
		component: () => import("./pages/Food.vue"),
	},
	{
		path: "/register",
		meta: { area: "register" },
		name: "register",
		component: () => import("./pages/Register.vue"),
	},
	{ path: "/staff", name: "staff", component: () => import("./pages/Staff.vue") },
	{ path: "/summary", name: "summary", component: () => import("./pages/Summary.vue") },
	{ path: "/activity", name: "activity", component: () => import("./pages/Activity.vue") },
	{
		path: "/verification",
		name: "verification",
		meta: { area: "rooms" },
		component: () => import("./pages/Verification.vue"),
	},
	{
		path: "/cash",
		name: "cash",
		meta: { area: ["payments", "expenses"] },
		component: () => import("./pages/Cash.vue"),
	},
	{
		path: "/notices",
		meta: { area: "notices" },
		name: "notices",
		component: () => import("./pages/Notices.vue"),
	},
	{ path: "/saas", name: "saas", component: () => import("./pages/Saas.vue") },
	{ path: "/billing", name: "billing", component: () => import("./pages/Billing.vue") },
	{ path: "/:pathMatch(.*)*", redirect: "/" },
];

const router = createRouter({
	history: createWebHistory("/rent/"),
	routes,
	scrollBehavior: () => ({ top: 0 }),
});

// staff logins only open the pages of their areas (the server checks it too)
router.beforeEach((to) => {
	if (!boot.access || to.meta.everyone || canUse(to.meta.area)) return true;
	return "/";
});

export default router;
