<template>
	<div>
		<PageHeader :title="`${greeting}, ${firstName}`" :subtitle="today">
			<Button :icon="Sparkles" @click="openDialog('generateInvoices')"
				>Generate invoices</Button
			>
			<Button
				variant="primary"
				:icon="Plus"
				class="max-sm:hidden"
				@click="openDialog('recordPayment')"
				>Record payment</Button
			>
		</PageHeader>

		<!-- quick actions, on phones -->
		<div class="mb-6 grid grid-cols-4 gap-2 sm:hidden">
			<component
				:is="a.to ? 'RouterLink' : 'button'"
				v-for="a in quickActions"
				:key="a.label"
				:to="a.to"
				class="card flex flex-col items-center gap-1.5 px-1 py-3 text-center text-[11px] leading-tight font-medium text-slate-700 active:bg-slate-50"
				@click="a.action && a.action()"
			>
				<span class="grid size-9 place-items-center rounded-xl" :class="a.tone"
					><component :is="a.icon" class="size-5"
				/></span>
				{{ a.label }}
			</component>
		</div>

		<!-- attention strip -->
		<div
			v-if="d && (d.draft_invoices || d.pending_deposits || d.outstanding.overdue_count)"
			class="mb-6 flex flex-wrap gap-2"
		>
			<RouterLink
				v-if="d.outstanding.overdue_count"
				to="/outstanding"
				class="pill bg-rose-50 text-rose-700 ring-rose-600/15"
			>
				<AlarmClock class="size-3.5" /> {{ d.outstanding.overdue_count }} overdue invoice{{
					d.outstanding.overdue_count > 1 ? "s" : ""
				}}
			</RouterLink>
			<RouterLink
				v-if="d.draft_invoices"
				:to="{ path: '/invoices', query: { status: 'Draft' } }"
				class="pill bg-amber-50 text-amber-700 ring-amber-600/20"
			>
				<FilePen class="size-3.5" /> {{ d.draft_invoices }} draft invoice{{
					d.draft_invoices > 1 ? "s" : ""
				}}
				to review
			</RouterLink>
			<RouterLink
				v-if="d.pending_deposits"
				to="/deposits"
				class="pill bg-sky-50 text-sky-700 ring-sky-600/15"
			>
				<ShieldCheck class="size-3.5" /> {{ d.pending_deposits }} deposit{{
					d.pending_deposits > 1 ? "s" : ""
				}}
				to settle
			</RouterLink>
		</div>

		<!-- KPIs -->
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
			<template v-if="d">
				<StatCard
					label="Occupancy"
					:value="`${d.rooms.occupancy}%`"
					:hint="`${d.rooms.occupied_beds} of ${d.rooms.beds} beds taken`"
					:icon="DoorOpen"
				>
					<div class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
						<div
							class="h-full rounded-full bg-brand-500 transition-all duration-700"
							:style="{ width: `${d.rooms.occupancy}%` }"
						/>
					</div>
				</StatCard>
				<StatCard
					label="Collected this month"
					:value="money(d.this_month.collected)"
					:hint="`of ${money(d.this_month.invoiced)} invoiced for ${d.this_month.month}`"
					:icon="Wallet"
					tone="green"
				/>
				<StatCard
					label="Outstanding"
					:value="money(d.outstanding.amount)"
					:hint="`${d.outstanding.count} unpaid invoice${
						d.outstanding.count === 1 ? '' : 's'
					}`"
					:icon="Hourglass"
					tone="amber"
				/>
				<StatCard
					label="Overdue"
					:value="money(d.outstanding.overdue_amount)"
					:hint="
						d.outstanding.overdue_count
							? `${d.outstanding.overdue_count} past due date`
							: 'Nothing overdue 🎉'
					"
					:icon="AlarmClock"
					tone="rose"
				/>
			</template>
			<Skeleton v-for="i in 4" v-else :key="i" class="h-36 rounded-2xl" />
		</div>

		<div class="mt-6 grid gap-6 lg:grid-cols-3">
			<div class="card p-5 lg:col-span-2">
				<div class="flex items-start justify-between">
					<div>
						<h2 class="font-semibold text-slate-900">Rent collection</h2>
						<p class="text-sm text-slate-500">Invoiced vs collected, last 6 months</p>
					</div>
					<p v-if="d" class="tabular text-right text-sm text-slate-500">
						<span class="block text-lg font-semibold text-slate-900"
							>{{ collectionRate }}%</span
						>collected
					</p>
				</div>
				<BarChart v-if="d" class="mt-4" :rows="trendRows" :series="series" />
				<Skeleton v-else class="mt-6 h-56" />
			</div>

			<div class="card p-5">
				<h2 class="font-semibold text-slate-900">Rooms</h2>
				<p class="min-h-5 text-sm text-slate-500">
					{{ d ? `${d.rooms.total} rooms, ${d.tenants} tenants staying` : "" }}
				</p>
				<template v-if="d">
					<div class="mt-5 flex h-3 overflow-hidden rounded-full bg-slate-100">
						<div
							v-for="s in roomStatuses"
							:key="s.status"
							:class="s.bar"
							:style="{ width: `${(s.count / (d.rooms.total || 1)) * 100}%` }"
						/>
					</div>
					<ul class="mt-5 space-y-3">
						<li
							v-for="s in roomStatuses"
							:key="s.status"
							class="flex items-center justify-between text-sm"
						>
							<span class="flex items-center gap-2.5 text-slate-600"
								><span class="size-2.5 rounded-full" :class="s.bar" />{{
									s.status
								}}</span
							>
							<span class="tabular font-medium text-slate-900">{{ s.count }}</span>
						</li>
					</ul>
					<Button class="mt-6 w-full" :icon="KeyRound" @click="openDialog('allotRoom')"
						>Allot a room</Button
					>
				</template>
			</div>
		</div>

		<div class="mt-6 grid gap-6 lg:grid-cols-2">
			<div class="card">
				<div class="flex items-center justify-between px-5 pt-5">
					<h2 class="font-semibold text-slate-900">Overdue invoices</h2>
					<RouterLink
						to="/outstanding"
						class="text-sm font-medium text-brand-600 hover:underline"
						>View all</RouterLink
					>
				</div>
				<ul v-if="d?.overdue_invoices.length" class="mt-3 divide-y divide-slate-100">
					<li
						v-for="inv in d.overdue_invoices"
						:key="inv.name"
						class="flex items-center gap-3 px-5 py-3"
					>
						<Avatar :name="inv.tenant_name" :image="inv.tenant_picture" size="sm" />
						<div class="min-w-0 flex-1">
							<p class="truncate text-sm font-medium">{{ inv.tenant_name }}</p>
							<p class="text-xs text-slate-500">
								Room {{ inv.room }} · {{ inv.billing_month }} ·
								<span class="text-rose-600"
									>{{ daysBetween(inv.due_date) }}d late</span
								>
							</p>
						</div>
						<p class="tabular text-sm font-semibold">
							{{ money(inv.outstanding_amount) }}
						</p>
						<Button size="sm" @click="openDialog('recordPayment', { invoice: inv })"
							>Collect</Button
						>
					</li>
				</ul>
				<EmptyState
					v-else-if="d"
					:icon="PartyPopper"
					title="No overdue rent"
					description="Every tenant is up to date."
				/>
			</div>

			<div class="card">
				<div class="flex items-center justify-between px-5 pt-5">
					<h2 class="font-semibold text-slate-900">Recent payments</h2>
					<RouterLink
						to="/payments"
						class="text-sm font-medium text-brand-600 hover:underline"
						>View all</RouterLink
					>
				</div>
				<ul v-if="d?.recent_payments.length" class="mt-3 divide-y divide-slate-100">
					<li
						v-for="p in d.recent_payments"
						:key="p.name"
						class="flex items-center gap-3 px-5 py-3"
					>
						<span
							class="grid size-7 place-items-center rounded-full bg-emerald-50 text-emerald-600"
							><ArrowDownLeft class="size-4"
						/></span>
						<div class="min-w-0 flex-1">
							<p class="truncate text-sm font-medium">{{ p.tenant_name }}</p>
							<p class="text-xs text-slate-500">
								{{ shortDate(p.payment_date) }} · {{ p.mode_of_payment }}
							</p>
						</div>
						<p class="tabular text-sm font-semibold text-emerald-600">
							+{{ money(p.amount) }}
						</p>
					</li>
				</ul>
				<EmptyState
					v-else-if="d"
					:icon="Wallet"
					title="No payments yet"
					description="Payments you record will show up here."
				/>
			</div>
		</div>

		<!-- coming up -->
		<div v-if="d && (d.moving_out.length || d.agreements_ending.length)" class="card mt-6">
			<div class="px-5 pt-5">
				<h2 class="font-semibold text-slate-900">Coming up</h2>
				<p class="text-sm text-slate-500">
					Move-outs and agreements ending in the next 30 days
				</p>
			</div>
			<ul class="mt-3 divide-y divide-slate-100">
				<li
					v-for="m in d.moving_out"
					:key="m.name"
					class="flex items-center gap-3 px-5 py-3"
				>
					<span
						class="grid size-7 place-items-center rounded-full bg-amber-50 text-amber-600"
						><LogOut class="size-4"
					/></span>
					<RouterLink
						:to="`/tenants/${m.tenant}`"
						class="min-w-0 flex-1 hover:underline"
					>
						<p class="truncate text-sm font-medium">{{ m.tenant_name }}</p>
						<p class="text-xs text-slate-500">
							Moving out of room {{ m.room }} · bed {{ m.bed_no }}
						</p>
					</RouterLink>
					<p class="text-sm font-medium text-amber-700">
						{{ shortDate(m.expected_vacate_date) }}
					</p>
				</li>
				<li
					v-for="a in d.agreements_ending"
					:key="a.name"
					class="flex items-center gap-3 px-5 py-3"
				>
					<span
						class="grid size-7 place-items-center rounded-full bg-sky-50 text-sky-600"
						><FileText class="size-4"
					/></span>
					<RouterLink
						:to="`/tenants/${a.tenant}`"
						class="min-w-0 flex-1 hover:underline"
					>
						<p class="truncate text-sm font-medium">{{ a.tenant_name }}</p>
						<p class="text-xs text-slate-500">Agreement ends · room {{ a.room }}</p>
					</RouterLink>
					<p class="text-sm font-medium text-sky-700">
						{{ shortDate(a.agreement_end_date) }}
					</p>
					<button
						class="rounded-lg px-2 py-1 text-xs font-medium text-brand-600 ring-1 ring-slate-200 hover:bg-slate-50"
						@click="
							openDialog('renewAgreement', {
								allotment: { name: a.name, tenant_name: a.tenant_name },
							})
						"
					>
						Renew
					</button>
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import {
	AlarmClock,
	ArrowDownLeft,
	DoorOpen,
	FilePen,
	FileText,
	Hourglass,
	KeyRound,
	LogOut,
	MoonStar,
	PartyPopper,
	Plus,
	ShieldCheck,
	Sparkles,
	UserPlus,
	Wallet,
} from "lucide-vue-next";
import { computed } from "vue";

import { get } from "@/api";
import Avatar from "@/components/Avatar.vue";
import BarChart from "@/components/BarChart.vue";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import { openDialog } from "@/dialogs";
import { boot, scope } from "@/store";
import { useResource } from "@/useResource";
import { date, daysBetween, money, shortDate } from "@/utils";

const quickActions = [
	{
		label: "Record payment",
		icon: Wallet,
		tone: "bg-emerald-50 text-emerald-600",
		action: () => openDialog("recordPayment"),
	},
	{
		label: "Night attendance",
		icon: MoonStar,
		tone: "bg-brand-50 text-brand-600",
		to: "/register",
	},
	{
		label: "Visitor at the gate",
		icon: DoorOpen,
		tone: "bg-sky-50 text-sky-600",
		to: "/register?tab=visitors&new=1",
	},
	{ label: "Add lead", icon: UserPlus, tone: "bg-amber-50 text-amber-600", to: "/leads?new=1" },
];

const { data } = useResource(() => get("get_dashboard", scope()));
const d = data;

const firstName = computed(() => (boot.full_name || "").split(" ")[0]);
const greeting = computed(() => {
	const hour = new Date().getHours();
	return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
});
const today = computed(() =>
	date(boot.today, { weekday: "long", day: "numeric", month: "long", year: "numeric" })
);

const series = [
	{ key: "invoiced", label: "Invoiced", color: "bg-brand-200" },
	{ key: "collected", label: "Collected", color: "bg-brand-600" },
];
const trendRows = computed(() => d.value.trend.map((t) => ({ ...t, short: t.month.slice(0, 3) })));
const collectionRate = computed(() => {
	const invoiced = d.value.trend.reduce((s, t) => s + t.invoiced, 0);
	const collected = d.value.trend.reduce((s, t) => s + t.collected, 0);
	return invoiced ? Math.min(100, Math.round((collected / invoiced) * 100)) : 0;
});

const statusBars = {
	Occupied: "bg-brand-500",
	"Partly Occupied": "bg-sky-400",
	Available: "bg-emerald-400",
	Reserved: "bg-amber-400",
	"Under Renovation": "bg-slate-300",
};
const roomStatuses = computed(() =>
	Object.entries(statusBars).map(([status, bar]) => ({
		status,
		bar,
		count: d.value.rooms.by_status[status] || 0,
	}))
);
</script>

<style scoped>
@reference "../style.css";
.pill {
	@apply inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition hover:brightness-95;
}
</style>
