<template>
	<div>
		<PageHeader
			:title="`${greeting}, ${firstName}`"
			:subtitle="[today, building].filter(Boolean).join(' · ')"
		/>

		<div v-if="actions.length" class="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
			<component
				:is="a.to ? 'RouterLink' : 'button'"
				v-for="a in actions"
				:key="a.label"
				:to="a.to"
				class="card flex flex-col items-center gap-2 px-2 py-4 text-center text-sm font-medium text-slate-700 transition hover:bg-slate-50 active:bg-slate-50"
				@click="a.action && a.action()"
			>
				<span class="grid size-11 place-items-center rounded-xl" :class="a.tone"
					><component :is="a.icon" class="size-5"
				/></span>
				{{ a.label }}
			</component>
		</div>

		<div class="grid gap-6 lg:grid-cols-[1fr_22rem]">
			<div class="space-y-4">
				<Skeleton v-if="!data" class="h-40" />
				<template v-else>
					<div v-if="data.register" class="card divide-y divide-slate-100">
						<RouterLink to="/register" class="row">
							<MoonStar class="size-5 text-brand-600" />
							<span class="flex-1">Night attendance</span>
							<span
								:class="
									data.register.attendance_taken
										? 'text-emerald-600'
										: 'text-amber-700'
								"
								>{{
									data.register.attendance_taken ? "Taken" : "Not taken yet"
								}}</span
							>
						</RouterLink>
						<RouterLink to="/register?tab=leave" class="row">
							<Luggage class="size-5 text-sky-600" />
							<span class="flex-1">Asking for leave</span>
							<span class="tabular font-semibold">{{
								data.register.leave_requests
							}}</span>
						</RouterLink>
						<RouterLink to="/register?tab=visitors" class="row">
							<DoorOpen class="size-5 text-violet-600" />
							<span class="flex-1">Visitors inside</span>
							<span class="tabular font-semibold">{{
								data.register.visitors_inside
							}}</span>
						</RouterLink>
					</div>

					<div
						v-if="'payments_to_confirm' in data"
						class="card divide-y divide-slate-100"
					>
						<RouterLink to="/payments" class="row">
							<Wallet class="size-5 text-emerald-600" />
							<span class="flex-1">Payments to confirm</span>
							<span class="tabular font-semibold">{{
								data.payments_to_confirm
							}}</span>
						</RouterLink>
						<RouterLink to="/outstanding" class="row">
							<AlarmClock class="size-5 text-rose-600" />
							<span class="flex-1">Overdue rent</span>
							<span class="tabular font-semibold">{{ data.overdue }}</span>
						</RouterLink>
					</div>

					<div v-if="data.unpaid" class="card">
						<div
							class="flex items-center justify-between border-b border-slate-100 px-5 py-4"
						>
							<div>
								<h3 class="font-semibold">Not paid yet</h3>
								<p class="text-xs text-slate-500">
									{{ data.unpaid.count }} tenant{{
										data.unpaid.count === 1 ? "" : "s"
									}}
									· {{ money(data.unpaid.owed) }}
								</p>
							</div>
							<RouterLink
								to="/outstanding"
								class="text-sm font-medium text-brand-600"
								>All</RouterLink
							>
						</div>
						<p
							v-if="!data.unpaid.rows.length"
							class="px-5 py-4 text-sm text-slate-500"
						>
							Everyone has paid. 🎉
						</p>
						<ul class="divide-y divide-slate-100">
							<li
								v-for="u in data.unpaid.rows"
								:key="u.invoice"
								class="flex flex-wrap items-center gap-3 px-5 py-3 text-sm"
							>
								<div class="min-w-0 flex-1">
									<p class="truncate font-medium">
										{{ u.tenant_name }}
										<span class="font-normal text-slate-500"
											>· room {{ u.room }}</span
										>
									</p>
									<p
										class="text-xs"
										:class="u.overdue ? 'text-rose-600' : 'text-slate-500'"
									>
										{{ money(u.owed) }} ·
										{{
											u.overdue
												? `${u.days_overdue} day${
														u.days_overdue === 1 ? "" : "s"
												  } late`
												: `due ${shortDate(u.due_on)}`
										}}
									</p>
								</div>
								<div class="flex gap-1">
									<a
										v-if="u.mobile_no"
										:href="`tel:${u.mobile_no}`"
										class="rounded-lg p-2 text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50"
										title="Call"
										><Phone class="size-4"
									/></a>
									<button
										v-if="u.reach.length"
										class="rounded-lg p-2 ring-1 ring-slate-200 hover:bg-slate-50"
										:class="
											u.reminded_today
												? 'text-emerald-600'
												: 'text-slate-500'
										"
										:disabled="u.reminded_today || reminding === u.invoice"
										:title="
											u.reminded_today ? 'Reminded today' : 'Send a reminder'
										"
										@click="remind(u)"
									>
										<Check v-if="u.reminded_today" class="size-4" /><Send
											v-else
											class="size-4"
										/>
									</button>
									<button
										class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200 hover:bg-emerald-50"
										@click="collect(u)"
									>
										Collected cash
									</button>
								</div>
							</li>
						</ul>
					</div>

					<div v-if="'new_leads' in data" class="card">
						<RouterLink to="/leads" class="row">
							<UserSearch class="size-5 text-amber-600" />
							<span class="flex-1">New leads to call</span>
							<span class="tabular font-semibold">{{ data.new_leads }}</span>
						</RouterLink>
					</div>

					<div v-if="data.food?.length" class="card p-5">
						<h3 class="font-semibold">Kitchen today</h3>
						<div class="mt-3 grid grid-cols-3 gap-3">
							<RouterLink
								v-for="m in data.food"
								:key="m.meal"
								to="/food"
								class="rounded-xl bg-slate-50 p-3 text-center"
							>
								<p class="text-xs text-slate-500">{{ m.meal }}</p>
								<p class="tabular text-2xl font-semibold">{{ m.eating }}</p>
								<p class="text-xs text-slate-400">to cook for</p>
							</RouterLink>
						</div>
					</div>

					<div v-if="data.requests" class="card">
						<RouterLink
							to="/requests"
							class="flex items-center justify-between border-b border-slate-100 px-5 py-4"
						>
							<h3 class="font-semibold">Open requests</h3>
							<ChevronRight class="size-4 text-slate-400" />
						</RouterLink>
						<p v-if="!data.requests.length" class="px-5 py-4 text-sm text-slate-500">
							Nothing open.
						</p>
						<ul class="divide-y divide-slate-100">
							<li
								v-for="r in data.requests"
								:key="r.name"
								class="flex items-center gap-3 px-5 py-3 text-sm"
							>
								<div class="min-w-0 flex-1">
									<p class="truncate font-medium">{{ r.subject }}</p>
									<p class="text-xs text-slate-500">
										Room {{ r.room || "–" }} · {{ r.priority }} priority
									</p>
								</div>
								<StatusBadge :status="r.status" />
							</li>
						</ul>
					</div>
				</template>
			</div>

			<div class="space-y-4">
				<ThisPhone :what="notifyWhat" />
				<p class="px-1 text-xs text-slate-500">
					Your login is for {{ areaNames }}. Ask your manager if you need more.
				</p>
			</div>
		</div>
	</div>
</template>

<script setup>
import {
	AlarmClock,
	Check,
	ChevronRight,
	DoorOpen,
	Luggage,
	Megaphone,
	MoonStar,
	Phone,
	Send,
	UserPlus,
	UserSearch,
	UtensilsCrossed,
	Wallet,
	Wrench,
	Zap,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import { get, post } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import ThisPhone from "@/components/ThisPhone.vue";
import { openDialog } from "@/dialogs";
import { boot, canUse, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { money, shortDate } from "@/utils";

const { data, reload } = useResource(() => get("get_staff_home", scope()));

const reminding = ref("");
async function remind(u) {
	reminding.value = u.invoice;
	try {
		const r = await post("send_bulk_reminders", { invoices: [u.invoice] });
		toast(
			r.sent
				? `Reminder sent to ${u.tenant_name}`
				: r.skipped[0]?.why || r.failed[0]?.why || "Not sent",
			r.sent ? "success" : "error"
		);
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		reminding.value = "";
	}
}
// into the warden's cash book (cash.py records who collected it)
function collect(u) {
	openDialog("recordPayment", {
		invoice: {
			name: u.invoice,
			outstanding_amount: u.bill_outstanding,
			tenant_name: u.tenant_name,
		},
		mode: "Cash",
	});
}

const hour = new Date().getHours();
const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
const firstName = (boot.access?.staff_name || boot.full_name || "").split(" ")[0];
const today = new Date(`${boot.today}T00:00:00`).toLocaleDateString("en-IN", {
	weekday: "long",
	day: "numeric",
	month: "long",
});
const building = boot.access?.building;

const actions = computed(() =>
	[
		canUse("payments") && {
			label: "Record payment",
			icon: Wallet,
			tone: "bg-emerald-50 text-emerald-600",
			action: () => openDialog("recordPayment"),
		},
		canUse("register") && {
			label: "Night attendance",
			icon: MoonStar,
			tone: "bg-brand-50 text-brand-600",
			to: "/register",
		},
		canUse("register") && {
			label: "Visitor at the gate",
			icon: DoorOpen,
			tone: "bg-sky-50 text-sky-600",
			to: "/register?tab=visitors&new=1",
		},
		canUse("requests") && {
			label: "Requests",
			icon: Wrench,
			tone: "bg-amber-50 text-amber-600",
			to: "/requests",
		},
		canUse("food") && {
			label: "Kitchen",
			icon: UtensilsCrossed,
			tone: "bg-emerald-50 text-emerald-600",
			to: "/food",
		},
		canUse("leads") && {
			label: "Add lead",
			icon: UserPlus,
			tone: "bg-amber-50 text-amber-600",
			to: "/leads?new=1",
		},
		canUse("meters") && {
			label: "Meter readings",
			icon: Zap,
			tone: "bg-yellow-50 text-yellow-700",
			to: "/electricity",
		},
		canUse("notices") && {
			label: "Notices",
			icon: Megaphone,
			tone: "bg-pink-50 text-pink-600",
			to: "/notices",
		},
	]
		.filter(Boolean)
		.slice(0, 8)
);

const NAMES = {
	rooms: "rooms and tenants",
	payments: "rent and payments",
	register: "the register",
	requests: "requests",
	food: "food",
	leads: "leads",
	meters: "electricity",
	expenses: "expenses",
	notices: "notices",
};
const areaNames = computed(() => {
	const names = Object.keys(NAMES)
		.filter((a) => boot.access?.areas.includes(a))
		.map((a) => NAMES[a]);
	return names.length > 1
		? `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`
		: names[0] || "nothing yet";
});
const notifyWhat = computed(() => {
	const parts = [
		canUse("register") && "leave requests",
		canUse("requests") && "new requests",
		canUse("payments") && "payments to confirm",
		canUse("leads") && "new leads",
	].filter(Boolean);
	return parts.length
		? `Notifications for ${parts.join(", ")}`
		: "Notifications from your manager";
});
</script>

<style scoped>
.row {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.875rem 1.25rem;
	font-size: 0.875rem;
}
.row:hover {
	background: rgb(248 250 252);
}
</style>
