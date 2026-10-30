<template>
	<div v-if="boot.loaded" class="min-h-screen lg:pl-64">
		<!-- sidebar -->
		<Transition
			enter-active-class="duration-200"
			enter-from-class="opacity-0"
			leave-active-class="duration-150"
			leave-to-class="opacity-0"
		>
			<div
				v-if="menuOpen"
				class="fixed inset-0 z-30 bg-slate-900/30 lg:hidden"
				@click="menuOpen = false"
			/>
		</Transition>
		<aside
			class="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-slate-200/80 bg-white transition-transform duration-200 lg:translate-x-0"
			:class="menuOpen ? 'translate-x-0' : '-translate-x-full'"
		>
			<div class="flex h-16 items-center gap-3 px-5">
				<img :src="logo" alt="" class="size-8" />
				<div class="leading-tight">
					<p class="text-sm font-semibold text-slate-900">Rent Management</p>
					<p class="text-xs text-slate-500">Property console</p>
				</div>
			</div>

			<div v-if="buildings.length > 1" class="px-3 pt-1">
				<label class="relative block">
					<Building2
						class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400"
					/>
					<select
						:value="ui.property"
						class="input pl-9 font-medium"
						aria-label="Building"
						@change="setProperty($event.target.value)"
					>
						<option value="">All buildings</option>
						<option v-for="b in buildings" :key="b.name" :value="b.name">
							{{ b.name }}
						</option>
					</select>
				</label>
			</div>

			<nav class="flex-1 space-y-6 overflow-y-auto px-3 py-4">
				<div v-for="group in nav" :key="group.label">
					<p
						class="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase"
					>
						{{ group.label }}
					</p>
					<RouterLink
						v-for="item in group.items"
						:key="item.to"
						:to="item.to"
						class="group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
						active-class="!bg-brand-50 !text-brand-700"
						@click="menuOpen = false"
					>
						<component
							:is="item.icon"
							class="size-[18px] shrink-0"
							:stroke-width="1.8"
						/>
						{{ item.label }}
						<span
							v-if="item.badge"
							class="ml-auto rounded-full bg-brand-600 px-1.5 text-[11px] leading-5 font-semibold text-white"
							>{{ item.badge }}</span
						>
					</RouterLink>
				</div>
			</nav>

			<div class="border-t border-slate-100 p-3">
				<RouterLink
					v-if="!pwa.installed && (pwa.installPrompt || isIOS)"
					to="/settings#this-phone"
					class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-brand-700 transition hover:bg-brand-50"
					@click="menuOpen = false"
				>
					<Smartphone class="size-4" /> Install the app
				</RouterLink>
				<a
					href="/app/tenant-space-allotment"
					class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
				>
					<ExternalLink class="size-4" /> Open Desk
				</a>
				<div class="mt-1 flex items-center gap-3 rounded-lg px-3 py-2">
					<Avatar :name="boot.full_name" :image="boot.user_image" size="sm" />
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-medium text-slate-900">
							{{ boot.full_name }}
						</p>
						<p class="truncate text-xs text-slate-500">{{ boot.user }}</p>
					</div>
					<button
						class="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
						title="Log out"
						@click="logout"
					>
						<LogOut class="size-4" />
					</button>
				</div>
			</div>
		</aside>

		<!-- mobile top bar -->
		<header
			class="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur lg:hidden"
		>
			<button
				class="-ml-1 rounded-lg p-2 text-slate-600 hover:bg-slate-100"
				@click="menuOpen = true"
			>
				<Menu class="size-5" />
			</button>
			<img :src="logo" alt="" class="size-7" />
			<p class="text-sm font-semibold">Rent Management</p>
		</header>

		<main class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
			<OfflineBanner />
			<div
				v-if="banner && $route.name !== 'billing'"
				class="mb-6 flex flex-col gap-3 rounded-xl border px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
				:class="bannerTones[banner.tone]"
			>
				<p class="flex items-center gap-2">
					<component :is="banner.icon" class="size-4 shrink-0" />{{ banner.text }}
				</p>
				<RouterLink to="/billing" class="font-semibold whitespace-nowrap underline">
					{{ banner.cta }}
				</RouterLink>
			</div>
			<RouterView v-slot="{ Component }">
				<Transition
					mode="out-in"
					enter-active-class="duration-150 ease-out"
					enter-from-class="opacity-0 translate-y-1"
					leave-active-class="duration-100"
					leave-to-class="opacity-0"
				>
					<component :is="Component" :key="$route.fullPath" />
				</Transition>
			</RouterView>
		</main>

		<component
			:is="dialogs[dialog.name]"
			v-if="dialog.name"
			v-bind="dialog.props"
			@close="closeDialog"
		/>
		<Toasts />
		<InstallSheet name="Rent Management" />
	</div>

	<div v-else class="grid min-h-screen place-items-center">
		<div
			class="size-8 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600"
		/>
	</div>
</template>

<script setup>
import {
	AlertTriangle,
	BarChart3,
	Briefcase,
	Building2,
	ClipboardList,
	Contact,
	CreditCard,
	DoorOpen,
	ExternalLink,
	FileText,
	FileUp,
	LayoutDashboard,
	Lock,
	LogOut,
	Menu,
	NotebookPen,
	Receipt,
	Settings,
	ShieldCheck,
	Smartphone,
	Sparkles,
	TrendingUp,
	Users,
	UserSearch,
	UtensilsCrossed,
	Wallet,
	Wrench,
	Zap,
} from "lucide-vue-next";
import { computed, defineAsyncComponent, ref } from "vue";

import Avatar from "./components/Avatar.vue";
import InstallSheet from "./components/InstallSheet.vue";
import OfflineBanner from "./components/OfflineBanner.vue";
import Toasts from "./components/Toasts.vue";
import { closeDialog, dialog } from "./dialogs";
import { forgetOfflineData, isIOS, pwa } from "./pwa";
import { activeProperties, boot, setProperty, ui } from "./store";
import { date } from "./utils";

const logo = `${import.meta.env.BASE_URL}favicon.svg`;
const menuOpen = ref(false);
const buildings = computed(() => activeProperties());

const nav = computed(() => [
	...(boot.is_control_site
		? [
				{
					label: "Your business",
					items: [{ to: "/saas", label: "Customers", icon: Briefcase }],
				},
		  ]
		: []),
	{
		label: "Overview",
		items: [
			{ to: "/", label: "Dashboard", icon: LayoutDashboard },
			{ to: "/summary", label: "Monthly report", icon: ClipboardList },
		],
	},
	{
		label: "Property",
		items: [
			{ to: "/leads", label: "Leads", icon: UserSearch, badge: boot.new_leads },
			{ to: "/rooms", label: "Rooms", icon: DoorOpen },
			{ to: "/tenants", label: "Tenants", icon: Users },
			{ to: "/requests", label: "Requests", icon: Wrench },
			{
				to: "/register",
				label: "Register",
				icon: NotebookPen,
				badge: boot.leave_requests,
			},
			...(boot.properties.some((p) => p.food_included && p.is_active)
				? [{ to: "/food", label: "Food", icon: UtensilsCrossed }]
				: []),
			{ to: "/staff", label: "Staff", icon: Contact },
			{ to: "/buildings", label: "Buildings", icon: Building2 },
			{ to: "/import", label: "Import", icon: FileUp },
		],
	},
	{
		label: "Billing",
		items: [
			{ to: "/invoices", label: "Invoices", icon: FileText },
			{ to: "/payments", label: "Payments", icon: Wallet },
			{ to: "/deposits", label: "Deposits", icon: ShieldCheck },
			{ to: "/electricity", label: "Electricity", icon: Zap },
			{ to: "/outstanding", label: "Outstanding", icon: BarChart3 },
			{ to: "/expenses", label: "Expenses", icon: Receipt },
			{ to: "/profit", label: "Profit & loss", icon: TrendingUp },
		],
	},
	{
		label: "Account",
		items: [
			{ to: "/settings", label: "Settings", icon: Settings },
			{ to: "/billing", label: "Subscription", icon: CreditCard },
		],
	},
]);

const bannerTones = {
	sky: "border-sky-200 bg-sky-50 text-sky-800",
	amber: "border-amber-200 bg-amber-50 text-amber-800",
	rose: "border-rose-200 bg-rose-50 text-rose-800",
};
const banner = computed(() => {
	const s = boot.subscription;
	if (!s?.enforced) return null;
	const days = (n) => `${n} day${n === 1 ? "" : "s"}`;
	if (s.status === "Expired")
		return {
			tone: "rose",
			icon: Lock,
			text: "Your subscription has expired, so the app is read-only. Renew to add or change anything.",
			cta: "Renew now",
		};
	if (s.status === "Past Due")
		return {
			tone: "amber",
			icon: AlertTriangle,
			text: `Your plan ended on ${date(s.current_period_end)}. Renew by ${date(
				s.grace_ends_on
			)} to keep using the app.`,
			cta: "Renew",
		};
	if (s.status === "Trial")
		return {
			tone: s.days_left <= 3 ? "amber" : "sky",
			icon: Sparkles,
			text: `${days(s.days_left)} left in your free trial of the ${s.plan_title} plan.`,
			cta: "Choose a plan",
		};
	if (s.days_left <= 7)
		return {
			tone: "amber",
			icon: AlertTriangle,
			text: `Your ${s.plan_title} plan ends in ${days(s.days_left)}.`,
			cta: "Renew",
		};
	return null;
});

const lazy = (name) => defineAsyncComponent(() => import(`./dialogs/${name}.vue`));
const dialogs = {
	allotRoom: lazy("AllotRoomDialog"),
	vacate: lazy("VacateDialog"),
	tenant: lazy("TenantDialog"),
	room: lazy("RoomDialog"),
	invoice: lazy("InvoiceDialog"),
	generateInvoices: lazy("GenerateInvoicesDialog"),
	recordPayment: lazy("RecordPaymentDialog"),
	settleDeposit: lazy("SettleDepositDialog"),
	collectDeposit: lazy("CollectDepositDialog"),
	property: lazy("PropertyDialog"),
	notice: lazy("NoticeDialog"),
	changeRent: lazy("ChangeRentDialog"),
	expense: lazy("ExpenseDialog"),
	request: lazy("RequestDialog"),
	lead: lazy("LeadDialog"),
	moveInLead: lazy("MoveInLeadDialog"),
	inspection: lazy("InspectionDialog"),
	mealPlan: lazy("MealPlanDialog"),
	staff: lazy("StaffDialog"),
	advance: lazy("AdvanceDialog"),
	paySalary: lazy("PaySalaryDialog"),
	splitInvoice: lazy("SplitInvoiceDialog"),
};

async function logout() {
	await forgetOfflineData(); // the last data loaded stays on the phone otherwise
	window.location.href = "/logout";
}
</script>
