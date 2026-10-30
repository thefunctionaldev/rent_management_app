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
	{ path: "/buildings", name: "buildings", component: () => import("./pages/Buildings.vue") },
	{ path: "/import", name: "import", component: () => import("./pages/Import.vue") },
	{ path: "/settings", name: "settings", component: () => import("./pages/Settings.vue") },
	{
		path: "/electricity",
		name: "electricity",
		component: () => import("./pages/Electricity.vue"),
	},
	{ path: "/expenses", name: "expenses", component: () => import("./pages/Expenses.vue") },
	{ path: "/profit", name: "profit", component: () => import("./pages/Profit.vue") },
	{ path: "/requests", name: "requests", component: () => import("./pages/Requests.vue") },
	{ path: "/leads", name: "leads", component: () => import("./pages/Leads.vue") },
	{ path: "/food", name: "food", component: () => import("./pages/Food.vue") },
	{ path: "/register", name: "register", component: () => import("./pages/Register.vue") },
	{ path: "/staff", name: "staff", component: () => import("./pages/Staff.vue") },
	{ path: "/summary", name: "summary", component: () => import("./pages/Summary.vue") },
	{ path: "/notices", name: "notices", component: () => import("./pages/Notices.vue") },
	{ path: "/saas", name: "saas", component: () => import("./pages/Saas.vue") },
	{ path: "/billing", name: "billing", component: () => import("./pages/Billing.vue") },
	{ path: "/:pathMatch(.*)*", redirect: "/" },
];

export default createRouter({
	history: createWebHistory("/rent/"),
	routes,
	scrollBehavior: () => ({ top: 0 }),
});
