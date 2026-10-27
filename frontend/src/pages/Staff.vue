<template>
	<div>
		<PageHeader
			title="Staff"
			subtitle="Who works at your buildings, their salaries and advances"
		>
			<div v-if="tab === 'salaries'" class="flex items-center gap-1">
				<button
					class="rounded-lg p-2 hover:bg-slate-100"
					title="Earlier"
					@click="shift(-1)"
				>
					<ChevronLeft class="size-4" />
				</button>
				<span class="w-36 text-center text-sm font-medium">{{ month }} {{ year }}</span>
				<button
					class="rounded-lg p-2 hover:bg-slate-100 disabled:opacity-30"
					title="Later"
					:disabled="isCurrentMonth"
					@click="shift(1)"
				>
					<ChevronRight class="size-4" />
				</button>
			</div>
			<Button
				v-if="tab === 'staff'"
				variant="primary"
				:icon="Plus"
				@click="openDialog('staff')"
				>Add staff</Button
			>
			<Button
				v-if="tab === 'advances'"
				variant="primary"
				:icon="Plus"
				:disabled="!staff.data?.staff.length"
				@click="openDialog('advance', { staff: staff.data.staff })"
				>Give advance</Button
			>
		</PageHeader>

		<Tabs v-model="tab" :tabs="tabs" class="mb-5" />

		<!-- salaries -->
		<template v-if="tab === 'salaries'">
			<div v-if="!pay.data" class="space-y-4">
				<Skeleton class="h-24" />
				<Skeleton class="h-64" />
			</div>
			<template v-else>
				<div class="mb-5 grid gap-4 sm:grid-cols-3">
					<StatCard
						label="Salaries this month"
						:value="money(pay.data.total)"
						:hint="`${pay.data.slips.length} people`"
						:icon="Wallet"
					/>
					<StatCard
						label="Paid"
						:value="money(pay.data.paid)"
						:icon="CircleCheck"
						tone="green"
					/>
					<StatCard
						label="Still to pay"
						:value="money(pay.data.total - pay.data.paid)"
						:icon="Clock"
						tone="amber"
					/>
				</div>

				<div
					v-if="pay.data.missing"
					class="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-800"
				>
					<span
						>{{ pay.data.missing }}
						{{ pay.data.missing === 1 ? "person has" : "people have" }} no salary slip
						for {{ month }} yet.</span
					>
					<Button size="sm" variant="primary" :loading="preparing" @click="prepare"
						>Prepare salaries</Button
					>
				</div>

				<EmptyState
					v-if="!pay.data.slips.length && !pay.data.missing"
					:icon="Contact"
					title="No salaries for this month"
					description="Add your warden, cook and cleaners on the Staff tab, then prepare their salaries here every month."
				/>
				<div v-else-if="pay.data.slips.length" class="card overflow-x-auto">
					<table class="w-full min-w-[56rem] text-sm">
						<thead class="bg-slate-50/60">
							<tr>
								<th class="table-head">Staff</th>
								<th class="table-head w-24 text-right">Days off</th>
								<th class="table-head text-right">Salary</th>
								<th class="table-head w-28 text-right">Bonus</th>
								<th class="table-head w-28 text-right">Deduction</th>
								<th class="table-head text-right">Advance</th>
								<th class="table-head text-right">Net pay</th>
								<th class="table-head w-48"></th>
							</tr>
						</thead>
						<tbody class="divide-y divide-slate-100">
							<tr v-for="s in pay.data.slips" :key="s.name">
								<td class="table-cell">
									<div class="flex items-center gap-3">
										<Avatar
											:name="s.staff_name"
											:image="s.staff_details?.display_picture"
											size="sm"
										/>
										<div>
											<p class="font-medium">{{ s.staff_name }}</p>
											<p class="text-xs text-slate-500">
												{{ s.role }}
												<template v-if="buildings > 1">
													· {{ s.property }}</template
												>
												<template v-if="s.days_employed < s.days_in_month">
													· worked {{ s.days_employed }} days</template
												>
											</p>
										</div>
									</div>
								</td>
								<td class="px-2 py-2 text-right">
									<input
										v-if="s.status === 'Draft'"
										v-model.number="s.unpaid_days"
										class="input tabular w-20 py-1 text-right"
										type="number"
										min="0"
										step="0.5"
										@change="save(s)"
									/>
									<span v-else class="tabular">{{ s.unpaid_days || "–" }}</span>
								</td>
								<td class="table-cell tabular text-right">
									{{ money(s.earned) }}
								</td>
								<td class="px-2 py-2 text-right">
									<input
										v-if="s.status === 'Draft'"
										v-model.number="s.bonus"
										class="input tabular w-24 py-1 text-right"
										type="number"
										min="0"
										@change="save(s)"
									/>
									<span v-else class="tabular">{{
										s.bonus ? money(s.bonus) : "–"
									}}</span>
								</td>
								<td class="px-2 py-2 text-right">
									<input
										v-if="s.status === 'Draft'"
										v-model.number="s.other_deduction"
										class="input tabular w-24 py-1 text-right"
										type="number"
										min="0"
										:title="s.deduction_note || ''"
										@change="save(s)"
									/>
									<span v-else class="tabular">{{
										s.other_deduction ? money(s.other_deduction) : "–"
									}}</span>
								</td>
								<td class="table-cell tabular text-right">
									<label
										v-if="s.status === 'Draft' && advanceDue(s)"
										class="inline-flex items-center gap-1.5"
										title="Recover advances from this salary"
									>
										<input
											v-model="s.recover_advances"
											type="checkbox"
											class="size-3.5 accent-brand-600"
											:true-value="1"
											:false-value="0"
											@change="save(s)"
										/>
										{{
											s.advance_recovery
												? `− ${money(s.advance_recovery)}`
												: "skip"
										}}
									</label>
									<template v-else>{{
										s.advance_recovery ? `− ${money(s.advance_recovery)}` : "–"
									}}</template>
								</td>
								<td class="table-cell tabular text-right font-semibold">
									{{ money(s.net_pay) }}
								</td>
								<td class="table-cell">
									<div class="flex items-center justify-end gap-2">
										<template v-if="s.status === 'Paid'">
											<span class="text-xs text-slate-500"
												>Paid {{ shortDate(s.paid_on) }}</span
											>
											<a
												v-if="s.staff_details?.mobile_no"
												:href="payslipLink(s)"
												target="_blank"
												class="rounded-lg p-1.5 text-emerald-600 hover:bg-emerald-50"
												title="Send the payslip on WhatsApp"
												><MessageCircle class="size-4"
											/></a>
											<button
												class="text-xs font-medium text-slate-500 hover:text-rose-600"
												@click="undo(s)"
											>
												Undo
											</button>
										</template>
										<Button
											v-else
											size="sm"
											variant="primary"
											@click="openDialog('paySalary', { slip: s, month })"
											>Pay</Button
										>
									</div>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
		</template>

		<!-- staff -->
		<template v-else-if="tab === 'staff'">
			<div v-if="!staff.data" class="grid gap-4 md:grid-cols-3">
				<Skeleton v-for="i in 3" :key="i" class="h-36" />
			</div>
			<EmptyState
				v-else-if="!staff.data.staff.length"
				:icon="Contact"
				title="No staff yet"
				description="Add the people who run your buildings: warden, cook, cleaners, security. Then pay their salaries here every month."
			/>
			<template v-else>
				<p class="mb-4 text-sm text-slate-500">
					{{ active.length }} working · {{ money(staff.data.monthly_total) }} a month in
					salaries<template v-if="staff.data.advance_due">
						· {{ money(staff.data.advance_due) }} in advances to recover</template
					>
				</p>
				<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
					<button
						v-for="s in staff.data.staff"
						:key="s.name"
						class="card flex flex-col p-5 text-left transition hover:ring-brand-200"
						:class="!s.is_active && 'opacity-60'"
						@click="openDialog('staff', { staff: s })"
					>
						<div class="flex items-center gap-3">
							<Avatar :name="s.staff_name" :image="s.display_picture" size="lg" />
							<div class="min-w-0">
								<p class="truncate font-semibold">{{ s.staff_name }}</p>
								<p class="text-sm text-slate-500">
									{{ s.role
									}}<template v-if="buildings > 1"> · {{ s.property }}</template>
								</p>
								<p v-if="s.mobile_no" class="text-sm text-slate-500">
									{{ s.mobile_no }}
								</p>
							</div>
						</div>
						<dl class="mt-4 grid grid-cols-2 gap-2 text-sm">
							<div>
								<dt class="text-xs text-slate-500">Salary</dt>
								<dd class="tabular font-medium">{{ money(s.monthly_salary) }}</dd>
							</div>
							<div>
								<dt class="text-xs text-slate-500">
									{{ s.is_active ? "Paid on" : "Left on" }}
								</dt>
								<dd>
									{{
										s.is_active
											? `${ordinal(s.pay_day)} of the month`
											: date(s.leaving_date)
									}}
								</dd>
							</div>
							<div v-if="s.advance_due" class="col-span-2">
								<dt class="text-xs text-slate-500">Advance to recover</dt>
								<dd class="tabular font-medium text-amber-700">
									{{ money(s.advance_due) }}
								</dd>
							</div>
						</dl>
					</button>
				</div>
			</template>
		</template>

		<!-- advances -->
		<template v-else>
			<EmptyState
				v-if="staff.data && !staff.data.advances.length"
				:icon="HandCoins"
				title="No advances"
				description="When you give someone part of their salary early, record it here. It's taken back from their next salaries."
			/>
			<div v-else-if="staff.data" class="card overflow-x-auto">
				<table class="w-full min-w-[40rem] text-sm">
					<thead class="bg-slate-50/60">
						<tr>
							<th class="table-head">Staff</th>
							<th class="table-head">Given</th>
							<th class="table-head text-right">Amount</th>
							<th class="table-head text-right">Per month</th>
							<th class="table-head text-right">To recover</th>
							<th class="table-head">Status</th>
							<th class="table-head"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr v-for="a in staff.data.advances" :key="a.name">
							<td class="table-cell">
								<p class="font-medium">{{ a.staff_name }}</p>
								<p v-if="a.note" class="text-xs text-slate-500">{{ a.note }}</p>
							</td>
							<td class="table-cell">{{ date(a.advance_date) }}</td>
							<td class="table-cell tabular text-right">{{ money(a.amount) }}</td>
							<td class="table-cell tabular text-right">
								{{ a.recover_per_month ? money(a.recover_per_month) : "All" }}
							</td>
							<td class="table-cell tabular text-right">
								{{ money(a.outstanding) }}
							</td>
							<td class="table-cell">
								<StatusBadge :status="a.status" />
							</td>
							<td class="table-cell text-right">
								<button
									v-if="!a.recovered"
									class="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
									title="Delete"
									@click="removeAdvance(a)"
								>
									<Trash2 class="size-4" />
								</button>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</template>
	</div>
</template>

<script setup>
import {
	ChevronLeft,
	ChevronRight,
	CircleCheck,
	Clock,
	Contact,
	HandCoins,
	MessageCircle,
	Plus,
	Trash2,
	Wallet,
} from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import Tabs from "@/components/Tabs.vue";
import { openDialog } from "@/dialogs";
import { activeProperties, boot, bumpData, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money, shortDate } from "@/utils";

const tab = ref("salaries");
const buildings = computed(() => activeProperties().length);

// salaries are paid for last month
const today = new Date(`${boot.today}T00:00:00`);
const cursor = ref(new Date(today.getFullYear(), today.getMonth() - 1, 1));
const month = computed(() => boot.months[cursor.value.getMonth()]);
const year = computed(() => cursor.value.getFullYear());
const isCurrentMonth = computed(
	() =>
		cursor.value.getFullYear() === today.getFullYear() &&
		cursor.value.getMonth() === today.getMonth()
);
function shift(n) {
	cursor.value = new Date(cursor.value.getFullYear(), cursor.value.getMonth() + n, 1);
}

// reactive() so the template reads pay.data rather than pay.data.value
const pay = reactive(
	useResource(() => get("get_salaries", { month: month.value, year: year.value, ...scope() }))
);
watch(cursor, pay.reload);
const staff = reactive(useResource(() => get("get_staff", scope())));

const active = computed(() => (staff.data?.staff || []).filter((s) => s.is_active));
const openAdvances = computed(
	() => (staff.data?.advances || []).filter((a) => a.status === "Open").length
);
const tabs = computed(() => [
	{ value: "salaries", label: "Salaries" },
	{ value: "staff", label: "Staff", count: active.value.length || undefined },
	{ value: "advances", label: "Advances", count: openAdvances.value || undefined },
]);

const advanceDue = (slip) =>
	slip.advance_recovery ||
	(staff.data?.staff || []).find((s) => s.name === slip.staff)?.advance_due;

const preparing = ref(false);
async function prepare() {
	preparing.value = true;
	try {
		const made = await post("prepare_salaries", {
			month: month.value,
			year: year.value,
			...scope(),
		});
		toast(`${made} salary slip${made === 1 ? "" : "s"} ready`);
		pay.reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		preparing.value = false;
	}
}

async function save(slip) {
	try {
		await post("save_salary_slip", {
			name: slip.name,
			data: {
				unpaid_days: slip.unpaid_days || 0,
				bonus: slip.bonus || 0,
				other_deduction: slip.other_deduction || 0,
				recover_advances: slip.recover_advances ? 1 : 0,
			},
		});
	} catch (e) {
		toast(e.message, "error");
	}
	pay.reload();
}

async function undo(slip) {
	if (!confirm(`Undo ${slip.staff_name}'s salary payment? Its expense is removed.`)) return;
	try {
		await post("undo_salary_payment", { name: slip.name });
		toast("Payment undone");
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	}
}

async function removeAdvance(a) {
	if (!confirm(`Delete the ${money(a.amount)} advance to ${a.staff_name}?`)) return;
	try {
		await post("delete_advance", { name: a.name });
		toast("Advance deleted");
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	}
}

const ordinal = (n) => {
	const s = ["th", "st", "nd", "rd"];
	const v = n % 100;
	return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

function payslipLink(s) {
	const digits = s.staff_details.mobile_no.replace(/[^\d]/g, "");
	const phone = digits.length === 10 ? `91${digits}` : digits;
	const lines = [
		`Hello ${s.staff_name}, your salary for ${month.value} ${year.value}:`,
		`Salary: ${money(s.earned)} (${s.days_paid} of ${s.days_in_month} days)`,
		s.bonus ? `Bonus: ${money(s.bonus)}` : null,
		s.other_deduction
			? `Deduction: ${money(s.other_deduction)}${
					s.deduction_note ? ` (${s.deduction_note})` : ""
			  }`
			: null,
		s.advance_recovery ? `Advance recovered: ${money(s.advance_recovery)}` : null,
		`Paid: ${money(s.net_pay)} on ${date(s.paid_on)}${
			s.mode_of_payment ? ` by ${s.mode_of_payment}` : ""
		}${s.reference_no ? ` (ref ${s.reference_no})` : ""}.`,
		"Thank you!",
	];
	return `https://wa.me/${phone}?text=${encodeURIComponent(lines.filter(Boolean).join("\n"))}`;
}
</script>
