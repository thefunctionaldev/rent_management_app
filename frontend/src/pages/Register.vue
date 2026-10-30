<template>
	<div>
		<PageHeader
			title="Register"
			subtitle="Night attendance, tenants on leave and visitors at the gate"
		>
			<input
				v-if="tab === 'night'"
				v-model="day"
				type="date"
				class="input w-40"
				:max="boot.today"
			/>
			<Button v-if="tab === 'leave'" variant="primary" @click="leaveForm = blankLeave()">
				<Plus class="size-4" /> Add leave
			</Button>
			<Button
				v-if="tab === 'visitors'"
				variant="primary"
				@click="visitorForm = blankVisitor()"
			>
				<Plus class="size-4" /> Visitor at the gate
			</Button>
		</PageHeader>

		<Tabs v-model="tab" :tabs="tabs" class="mb-5" />

		<div v-if="loading && !data" class="space-y-4">
			<Skeleton class="h-24" />
			<Skeleton class="h-72" />
		</div>

		<!-- night attendance -->
		<template v-else-if="tab === 'night'">
			<EmptyState
				v-if="!data?.buildings.length"
				:icon="MoonStar"
				title="No buildings yet"
				description="Add a building and move tenants in to take night attendance."
			/>
			<section v-for="b in data?.buildings || []" :key="b.name" class="card mb-6">
				<div
					class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4"
				>
					<div>
						<h2 class="font-semibold">{{ b.name }}</h2>
						<p class="text-xs text-slate-500">
							{{ date(b.date) }}
							<template v-if="b.curfew"> · gate closes {{ b.curfew }}</template>
							· {{ b.taken ? "taken" : "not taken yet" }}
						</p>
					</div>
					<div class="flex flex-wrap items-center gap-2 text-xs">
						<span
							v-for="s in counted"
							:key="s"
							class="tabular rounded-full px-2.5 py-1"
							:class="tone[s]"
							>{{ count(b, s) }} {{ s.toLowerCase() }}</span
						>
						<span
							v-if="count(b, null)"
							class="tabular rounded-full bg-slate-100 px-2.5 py-1 text-slate-600"
							>{{ count(b, null) }} not marked</span
						>
					</div>
				</div>
				<p v-if="!b.rows.length" class="px-5 py-8 text-center text-sm text-slate-500">
					Nobody is staying here on this night.
				</p>
				<ul v-else class="divide-y divide-slate-100">
					<li
						v-for="row in b.rows"
						:key="row.allotment"
						class="px-5 py-3"
						:class="missing(row) && 'bg-rose-50/60'"
					>
						<div class="flex flex-wrap items-center gap-3">
							<Avatar :name="row.tenant_name" :image="row.picture" size="sm" />
							<div class="min-w-40 flex-1">
								<RouterLink
									:to="`/tenants/${row.tenant}`"
									class="font-medium hover:underline"
									>{{ row.tenant_name }}</RouterLink
								>
								<p class="text-xs text-slate-500">
									Room {{ row.room
									}}<template v-if="row.bed_no">
										· bed {{ row.bed_no }}</template
									>
									<template v-if="row.on_leave">
										· on leave until {{ date(row.leave_until) }}</template
									>
								</p>
							</div>
							<div class="flex overflow-hidden rounded-lg ring-1 ring-slate-200">
								<button
									v-for="s in marks"
									:key="s"
									type="button"
									class="px-3 py-1.5 text-xs font-medium transition"
									:class="
										row.status === s
											? toneOn[s]
											: 'bg-white text-slate-500 hover:bg-slate-50'
									"
									@click="row.status = row.status === s ? null : s"
								>
									{{ s }}
								</button>
							</div>
						</div>
						<div
							v-if="row.status === 'Late' || row.status === 'Absent' || row.note"
							class="mt-2 flex flex-wrap items-center gap-2 pl-10 text-xs"
						>
							<input
								v-model="row.note"
								class="input w-56 flex-1 py-1 text-xs"
								:placeholder="
									row.status === 'Late' ? 'Came in at…' : 'Where are they?'
								"
							/>
							<template v-if="missing(row)">
								<a
									v-if="row.mobile_no"
									:href="`tel:${row.mobile_no}`"
									class="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 font-medium text-slate-700 ring-1 ring-slate-200"
									><Phone class="size-3" /> Call
									{{ row.tenant_name.split(" ")[0] }}</a
								>
								<a
									v-if="row.emergency.phone"
									:href="emergencyLink(row)"
									target="_blank"
									class="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2.5 py-1 font-medium text-white"
									><MessageCircle class="size-3" /> WhatsApp
									{{ row.emergency.name || "emergency contact"
									}}<template v-if="row.emergency.relation">
										({{ row.emergency.relation.toLowerCase() }})</template
									></a
								>
								<span v-else class="text-rose-700"
									>No emergency contact saved</span
								>
							</template>
						</div>
					</li>
				</ul>
				<div
					v-if="b.rows.length"
					class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-5 py-3"
				>
					<button
						type="button"
						class="text-sm font-medium text-brand-600 hover:underline"
						@click="b.rows.forEach((r) => !r.status && (r.status = 'Present'))"
					>
						Mark the rest present
					</button>
					<Button
						variant="primary"
						:loading="saving === b.name"
						@click="saveAttendance(b)"
						>Save attendance</Button
					>
				</div>
				<div
					v-if="b.history.length"
					class="flex gap-2 overflow-x-auto border-t border-slate-100 px-5 py-3"
				>
					<button
						v-for="h in b.history"
						:key="h.name"
						type="button"
						class="shrink-0 rounded-lg px-2.5 py-1.5 text-left text-xs ring-1 ring-slate-200 hover:bg-slate-50"
						:class="h.date === b.date && 'bg-brand-50 ring-brand-200'"
						@click="day = h.date"
					>
						<span class="block font-medium">{{ shortDate(h.date) }}</span>
						<span class="tabular text-slate-500"
							>{{ h.present + h.late }} in<template v-if="h.absent">
								·
								<b class="text-rose-600">{{ h.absent }} absent</b></template
							></span
						>
					</button>
				</div>
			</section>
		</template>

		<!-- leave -->
		<div v-else-if="tab === 'leave'" class="space-y-6">
			<EmptyState
				v-if="!leaveCount"
				:icon="Luggage"
				title="Nobody is on leave"
				description="Tenants ask for leave from the tenant app. Approved leave shows at night attendance and their meals are skipped."
			/>
			<div v-for="group in leaveGroups" :key="group.key">
				<template v-if="data.leaves[group.key].length">
					<h3 class="mb-2 text-sm font-semibold text-slate-700">{{ group.label }}</h3>
					<ul class="card divide-y divide-slate-100">
						<li
							v-for="l in data.leaves[group.key]"
							:key="l.name"
							class="flex flex-wrap items-center gap-3 px-5 py-3"
						>
							<div class="min-w-48 flex-1">
								<p class="font-medium">
									{{ l.tenant_name }}
									<span class="text-xs font-normal text-slate-500"
										>· room {{ l.room }}</span
									>
								</p>
								<p class="text-sm text-slate-600">
									{{ shortDate(l.from_date) }} – {{ date(l.to_date) }}
									<span class="text-slate-400"
										>({{ nights(l) }} night{{
											nights(l) === 1 ? "" : "s"
										}})</span
									>
									<template v-if="l.destination">
										· {{ l.destination }}</template
									>
								</p>
								<p v-if="l.reason" class="text-xs text-slate-500">
									{{ l.reason }}
								</p>
								<p v-if="l.decision_note" class="text-xs text-slate-500 italic">
									{{ l.decision_note }}
								</p>
							</div>
							<StatusBadge v-if="group.key === 'recent'" :status="l.status" />
							<template v-if="group.key === 'requested'">
								<Button size="sm" @click="decide(l, 0)">Reject</Button>
								<Button size="sm" variant="primary" @click="decide(l, 1)"
									>Approve</Button
								>
							</template>
							<Button
								v-else-if="group.key !== 'recent'"
								size="sm"
								@click="cancelLeave(l)"
								>Cancel leave</Button
							>
						</li>
					</ul>
				</template>
			</div>
		</div>

		<!-- visitors -->
		<div v-else class="space-y-6">
			<EmptyState
				v-if="!visitorCount"
				:icon="DoorOpen"
				title="No visitors today"
				description="Check visitors in at the gate. Tenants can also tell you from the tenant app who is coming."
			/>
			<div v-for="group in visitorGroups" :key="group.key">
				<template v-if="data.visitors[group.key].length">
					<h3 class="mb-2 text-sm font-semibold text-slate-700">{{ group.label }}</h3>
					<ul class="card divide-y divide-slate-100">
						<li
							v-for="v in data.visitors[group.key]"
							:key="v.name"
							class="flex flex-wrap items-center gap-3 px-5 py-3"
						>
							<div class="min-w-48 flex-1">
								<p class="font-medium">
									{{ v.visitor_name }}
									<span
										v-if="v.overnight"
										class="ml-1 rounded-full bg-violet-50 px-2 py-0.5 text-xs font-normal text-violet-700"
										>overnight</span
									>
								</p>
								<p class="text-sm text-slate-600">
									{{
										[v.tenant_name && `Visiting ${v.tenant_name}`, v.purpose]
											.filter(Boolean)
											.join(" · ")
									}}
									<a
										v-if="v.visitor_phone"
										:href="`tel:${v.visitor_phone}`"
										class="text-slate-500 hover:underline"
										>{{ v.visitor_phone }}</a
									>
								</p>
								<p class="text-xs text-slate-500">
									<template v-if="v.status === 'Expected'"
										>Expected {{ date(v.expected_on) }} · told by the
										tenant</template
									>
									<template v-else>
										In {{ time(v.check_in) }}
										<template v-if="group.key === 'recent'">
											on {{ shortDate(v.check_in.slice(0, 10)) }}</template
										>
										<template v-if="v.check_out">
											· out {{ time(v.check_out) }}</template
										>
										<b v-if="v.after_hours" class="text-amber-700">
											· after visiting hours</b
										>
									</template>
								</p>
							</div>
							<template v-if="v.status === 'Expected'">
								<Button size="sm" @click="cancelVisitor(v)">Didn't come</Button>
								<Button size="sm" variant="primary" @click="arrived(v)"
									>Arrived</Button
								>
							</template>
							<Button
								v-else-if="v.status === 'Inside'"
								size="sm"
								variant="primary"
								@click="left(v)"
								>Left</Button
							>
						</li>
					</ul>
				</template>
			</div>
		</div>

		<!-- add leave -->
		<Modal
			:open="!!leaveForm"
			title="Add leave"
			subtitle="Approved straight away. Their meals on those days are skipped."
			@close="leaveForm = null"
		>
			<form v-if="leaveForm" id="leave-form" class="space-y-4" @submit.prevent="addLeave">
				<Field label="Tenant">
					<select v-model="leaveForm.allotment" class="input" required>
						<option value="" disabled>Choose a tenant</option>
						<option v-for="s in stays" :key="s.allotment" :value="s.allotment">
							{{ s.tenant_name }} · room {{ s.room }}
						</option>
					</select>
				</Field>
				<div class="grid gap-3 sm:grid-cols-2">
					<Field label="Leaving on">
						<input v-model="leaveForm.from_date" type="date" class="input" required />
					</Field>
					<Field label="Back on" hint="the last night away">
						<input
							v-model="leaveForm.to_date"
							type="date"
							class="input"
							:min="leaveForm.from_date"
							required
						/>
					</Field>
				</div>
				<Field label="Going to">
					<input
						v-model="leaveForm.destination"
						class="input"
						placeholder="Home, Mysuru"
					/>
				</Field>
				<Field label="Reason">
					<input v-model="leaveForm.reason" class="input" placeholder="Festival" />
				</Field>
			</form>
			<template #footer>
				<Button @click="leaveForm = null">Cancel</Button>
				<Button variant="primary" type="submit" form="leave-form" :loading="busy"
					>Add leave</Button
				>
			</template>
		</Modal>

		<!-- visitor at the gate -->
		<Modal :open="!!visitorForm" title="Visitor at the gate" @close="visitorForm = null">
			<form
				v-if="visitorForm"
				id="visitor-form"
				class="space-y-4"
				@submit.prevent="checkIn(visitorForm)"
			>
				<div class="grid gap-3 sm:grid-cols-2">
					<Field label="Visitor's name">
						<input v-model="visitorForm.visitor_name" class="input" required />
					</Field>
					<Field label="Phone">
						<input v-model="visitorForm.visitor_phone" class="input" type="tel" />
					</Field>
				</div>
				<Field label="Visiting">
					<select v-model="visitorForm.tenant" class="input">
						<option value="">Nobody in particular</option>
						<option v-for="s in stays" :key="s.allotment" :value="s.tenant">
							{{ s.tenant_name }} · room {{ s.room }}
						</option>
					</select>
				</Field>
				<Field v-if="!visitorForm.tenant && buildings.length > 1" label="Building">
					<select v-model="visitorForm.property" class="input" required>
						<option v-for="b in buildings" :key="b.name" :value="b.name">
							{{ b.name }}
						</option>
					</select>
				</Field>
				<Field label="Purpose">
					<input
						v-model="visitorForm.purpose"
						class="input"
						placeholder="Parent, friend, delivery, plumber…"
					/>
				</Field>
				<label class="flex items-center gap-2 text-sm text-slate-700">
					<input
						v-model="visitorForm.overnight"
						type="checkbox"
						class="size-4 accent-brand-600"
					/>
					Staying overnight
				</label>
			</form>
			<template #footer>
				<Button @click="visitorForm = null">Cancel</Button>
				<Button variant="primary" type="submit" form="visitor-form" :loading="busy"
					>Check in</Button
				>
			</template>
		</Modal>
	</div>
</template>

<script setup>
import { DoorOpen, Luggage, MessageCircle, MoonStar, Phone, Plus } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { get, post } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import Tabs from "@/components/Tabs.vue";
import { boot, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, daysBetween, shortDate } from "@/utils";

const route = useRoute();
const tab = ref(["leave", "visitors"].includes(route.query.tab) ? route.query.tab : "night");
const day = ref(boot.today);
const { data, loading, reload } = useResource(() =>
	get("get_register", { day: day.value, ...scope() })
);
watch(day, reload);
// keep the nav badge in step after approving or rejecting
watch(data, (d) => d && !scope().property && (boot.leave_requests = d.leaves.requested.length));

const marks = ["Present", "Late", "Absent", "On Leave"];
const counted = ["Present", "Late", "Absent", "On Leave"];
const tone = {
	Present: "bg-emerald-50 text-emerald-700",
	Late: "bg-amber-50 text-amber-800",
	Absent: "bg-rose-50 text-rose-700",
	"On Leave": "bg-sky-50 text-sky-700",
};
const toneOn = {
	Present: "bg-emerald-600 text-white",
	Late: "bg-amber-500 text-white",
	Absent: "bg-rose-600 text-white",
	"On Leave": "bg-sky-600 text-white",
};
const count = (b, status) => b.rows.filter((r) => (r.status || null) === status).length;
// absent without leave: the one to worry about
const missing = (row) => row.status === "Absent" && !row.on_leave;

const buildings = computed(() => data.value?.buildings || []);
const stays = computed(() =>
	buildings.value
		.flatMap((b) => b.rows)
		.sort((a, b) => a.tenant_name.localeCompare(b.tenant_name))
);

const leaveGroups = [
	{ key: "requested", label: "Asking for leave" },
	{ key: "away", label: "Away now" },
	{ key: "upcoming", label: "Coming up" },
	{ key: "recent", label: "Recent" },
];
const visitorGroups = [
	{ key: "inside", label: "Inside now" },
	{ key: "expected", label: "Expected" },
	{ key: "today", label: "Earlier today" },
	{ key: "recent", label: "Last two weeks" },
];
const leaveCount = computed(() =>
	leaveGroups.reduce((n, g) => n + (data.value?.leaves[g.key].length || 0), 0)
);
const visitorCount = computed(() =>
	visitorGroups.reduce((n, g) => n + (data.value?.visitors[g.key].length || 0), 0)
);
const tabs = computed(() => [
	{ value: "night", label: "Night attendance" },
	{ value: "leave", label: "Leave", count: data.value?.leaves.requested.length || undefined },
	{
		value: "visitors",
		label: "Visitors",
		count: data.value?.visitors.inside.length || undefined,
	},
]);

const nights = (l) => daysBetween(l.from_date, l.to_date) + 1;
const time = (value) =>
	value
		? new Date(value.replace(" ", "T")).toLocaleTimeString("en-IN", {
				hour: "numeric",
				minute: "2-digit",
		  })
		: "";

function emergencyLink(row) {
	const digits = row.emergency.phone.replace(/[^\d]/g, "");
	const phone = digits.length === 10 ? `91${digits}` : digits;
	const text =
		`Hello${row.emergency.name ? ` ${row.emergency.name}` : ""}, this is the warden at ` +
		`${row.room ? `room ${row.room}'s ` : ""}hostel. ${row.tenant_name} hasn't come back ` +
		`tonight and we couldn't reach them. Do you know where they are? Please let us know.`;
	return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
}

const saving = ref(null);
async function saveAttendance(b) {
	saving.value = b.name;
	try {
		await post("save_attendance", {
			property: b.name,
			date: b.date,
			entries: b.rows.map((r) => ({
				allotment: r.allotment,
				status: r.status,
				note: r.note,
			})),
		});
		toast("Attendance saved");
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = null;
	}
}

const busy = ref(false);
async function act(method, args, message) {
	busy.value = true;
	try {
		await post(method, args);
		toast(message);
		await reload();
		return true;
	} catch (e) {
		toast(e.message, "error");
		return false;
	} finally {
		busy.value = false;
	}
}

const blankLeave = () => ({
	allotment: "",
	from_date: boot.today,
	to_date: boot.today,
	destination: "",
	reason: "",
});
const leaveForm = ref(null);
async function addLeave() {
	if (await act("add_leave", leaveForm.value, "Leave added")) leaveForm.value = null;
}
const decide = (l, approve) =>
	act("decide_leave", { name: l.name, approve }, approve ? "Leave approved" : "Leave rejected");
const cancelLeave = (l) => act("cancel_leave", { name: l.name }, "Leave cancelled");

const blankVisitor = () => ({
	visitor_name: "",
	visitor_phone: "",
	tenant: "",
	property: scope().property || buildings.value[0]?.name || "",
	purpose: "",
	overnight: false,
});
const visitorForm = ref(null);
// "Visitor at the gate" on the phone's home screen
if (route.query.new && tab.value === "visitors")
	watch(data, (d) => d && !visitorForm.value && (visitorForm.value = blankVisitor()), {
		immediate: true,
	});
async function checkIn(form) {
	const ok = await act(
		"visitor_in",
		{ data: { ...form, overnight: form.overnight ? 1 : 0 } },
		`${form.visitor_name} checked in`
	);
	if (ok) visitorForm.value = null;
}
const arrived = (v) => checkIn({ name: v.name, visitor_name: v.visitor_name });
const left = (v) => act("visitor_out", { name: v.name }, `${v.visitor_name} left`);
const cancelVisitor = (v) => act("cancel_visitor", { name: v.name }, "Visitor removed");
</script>
