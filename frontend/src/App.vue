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
					</RouterLink>
				</div>
			</nav>

			<div class="border-t border-slate-100 p-3">
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
	CreditCard,
	DoorOpen,
	ExternalLink,
	FileText,
	LayoutDashboard,
	Lock,
	LogOut,
	Menu,
	ShieldCheck,
	Sparkles,
	Users,
	Wallet,
} from "lucide-vue-next";
import { computed, defineAsyncComponent, ref } from "vue";

import Avatar from "./components/Avatar.vue";
import Toasts from "./components/Toasts.vue";
import { closeDialog, dialog } from "./dialogs";
import { boot } from "./store";
import { date } from "./utils";

const logo = `${import.meta.env.BASE_URL}favicon.svg`;
const menuOpen = ref(false);

const nav = [
	{
		label: "Overview",
		items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard }],
	},
	{
		label: "Property",
		items: [
			{ to: "/rooms", label: "Rooms", icon: DoorOpen },
			{ to: "/tenants", label: "Tenants", icon: Users },
		],
	},
	{
		label: "Billing",
		items: [
			{ to: "/invoices", label: "Invoices", icon: FileText },
			{ to: "/payments", label: "Payments", icon: Wallet },
			{ to: "/deposits", label: "Deposits", icon: ShieldCheck },
			{ to: "/outstanding", label: "Outstanding", icon: BarChart3 },
		],
	},
	{
		label: "Account",
		items: [{ to: "/billing", label: "Subscription", icon: CreditCard }],
	},
];

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
};

function logout() {
	window.location.href = "/logout";
}
</script>
