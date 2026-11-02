<template>
	<div class="space-y-6">
		<header class="flex flex-wrap items-start justify-between gap-4">
			<div>
				<p class="text-sm text-slate-500">{{ $t("Property operations") }}</p>
				<h1 class="text-3xl font-semibold tracking-tight">{{ $t(config.title) }}</h1>
				<p class="mt-2 max-w-2xl text-sm text-slate-500">{{ $t(config.hint) }}</p>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button :loading="busy" @click="load">{{ $t("Refresh") }}</Button
				><Button v-if="manager || kind === 'waitlist'" variant="primary" @click="edit()">{{
					$t(config.create)
				}}</Button
				><Button v-if="kind === 'workorders' && manager" @click="vendor">{{
					$t("Add vendor")
				}}</Button
				><Button
					v-if="manager && ['recurring', 'housekeeping'].includes(kind)"
					:disabled="busy"
					@click="run(kind + '.generate_now')"
					>{{ $t("Generate due items") }}</Button
				>
			</div>
		</header>
		<p v-if="error" role="alert" class="rounded-xl bg-rose-50 p-4 text-rose-700">{{ error }}</p>
		<p v-if="notice" role="status" class="rounded-xl bg-sky-50 p-4 text-sky-800">
			{{ notice }}
		</p>
		<div class="flex flex-wrap gap-3">
			<input
				v-model="search"
				class="input max-w-sm"
				:placeholder="$t('Search')"
				:aria-label="$t('Search')"
			/><select v-model="filter" class="input max-w-xs" :aria-label="$t('Status')">
				<option value="">{{ $t("All statuses") }}</option>
				<option v-for="s in statuses" :key="s" :value="s">{{ $t(s) }}</option>
			</select>
		</div>
		<p v-if="busy" role="status">{{ $t("Loading…") }}</p>
		<div v-else-if="!filtered.length" class="card p-10 text-center text-slate-500">
			{{ $t("No items to show.") }}
		</div>
		<div class="grid gap-4 xl:grid-cols-2">
			<article v-for="r in filtered" :key="r.name" class="card space-y-4 p-5">
				<div class="flex justify-between gap-3">
					<div>
						<h2 class="text-lg font-semibold">
							{{ r.subject || r.title || r.full_name }}
						</h2>
						<p class="text-xs text-slate-500">{{ r.property }} · {{ r.name }}</p>
					</div>
					<span class="h-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-medium">{{
						$t(r.status)
					}}</span>
				</div>
				<dl class="grid grid-cols-2 gap-3 text-sm">
					<template
						v-for="k in config.details.filter(
							(k) => r[k] !== null && r[k] !== undefined && r[k] !== '',
						)"
						:key="k"
						><div>
							<dt class="text-slate-500">{{ $t(label(k)) }}</dt>
							<dd class="break-words font-medium">{{ r[k] }}</dd>
						</div></template
					>
				</dl>
				<p v-if="overdue(r)" class="text-sm font-medium text-rose-600">
					{{ $t("Overdue") }}
				</p>
				<template v-if="kind === 'housekeeping'"
					><label
						v-for="(item, i) in checklist(r)"
						:key="i"
						class="flex items-center gap-2 text-sm"
						><input
							v-model="checks[r.name]"
							type="checkbox"
							:value="i"
							:disabled="r.status !== 'Open'"
						/>{{ item.label }}<span v-if="item.done">✓</span></label
					></template
				>
				<div
					v-if="kind === 'workorders' || kind === 'housekeeping'"
					class="flex flex-wrap gap-3 text-sm"
				>
					<template
						v-for="field in kind === 'workorders'
							? ['before_photo', 'after_photo']
							: ['photo']"
						:key="field"
					>
						<a
							v-if="r[field]"
							:href="download(config.doctype, r.name, field)"
							class="text-brand-600 underline"
							>{{ $t(label(field)) }}</a
						>
						<label v-if="canUpload(r)" class="cursor-pointer text-brand-600"
							>{{ $t("Upload") }} {{ $t(label(field))
							}}<input
								class="sr-only"
								type="file"
								accept="image/png,image/jpeg,image/webp"
								:disabled="busy"
								@change="attach(r, field, $event)"
						/></label>
					</template>
				</div>
				<div class="flex flex-wrap gap-2">
					<template v-if="kind === 'workorders'">
						<Button v-if="r.status === 'Draft' && manager" @click="edit(r)">{{
							$t("Edit")
						}}</Button>
						<Button
							v-for="a in orderActions(r)"
							:key="a"
							:disabled="busy"
							@click="orderAction(r, a)"
							>{{ $t(label(a)) }}</Button
						>
						<Button
							v-if="
								manager &&
								['Completed', 'Confirmed'].includes(r.status) &&
								!r.expense &&
								r.actual_cost > 0
							"
							@click="payment(r, 'pay_work_order')"
							>{{ $t("Record payment") }}</Button
						>
					</template>
					<template v-if="kind === 'recurring' && manager && r.status === 'Due'"
						><Button @click="payment(r, 'pay_operating_bill')">{{
							$t("Record payment")
						}}</Button
						><Button
							@click="reason('Cancel bill', 'recurring.cancel_bill', r, 'reason')"
							>{{ $t("Cancel") }}</Button
						></template
					>
					<template v-if="kind === 'housekeeping'"
						><Button v-if="r.status === 'Open'" @click="finishTask(r)">{{
							$t("Complete")
						}}</Button
						><template v-if="manager && r.status !== 'Open'"
							><Button
								v-if="r.status === 'Completed'"
								@click="
									run('housekeeping.update_task', {
										name: r.name,
										action: 'verify',
									})
								"
								>{{ $t("Verify") }}</Button
							><Button
								@click="
									run('housekeeping.update_task', {
										name: r.name,
										action: 'reopen',
									})
								"
								>{{ $t("Reopen") }}</Button
							></template
						></template
					>
					<template v-if="kind === 'waitlist'"
						><Button v-if="r.status === 'Waiting'" @click="edit(r)">{{
							$t("Edit")
						}}</Button
						><Button
							v-if="['Waiting', 'Offered'].includes(r.status)"
							@click="match(r)"
							>{{ $t("Find matches") }}</Button
						><Button
							v-if="r.status === 'Offered'"
							@click="run('waitlist.act', { name: r.name, action: 'accept' })"
							>{{ $t("Accept and create lead") }}</Button
						><Button
							v-if="r.status === 'Offered'"
							@click="run('waitlist.act', { name: r.name, action: 'withdraw' })"
							>{{ $t("Withdraw") }}</Button
						><Button
							v-if="['Waiting', 'Offered'].includes(r.status)"
							@click="run('waitlist.act', { name: r.name, action: 'close' })"
							>{{ $t("Close") }}</Button
						><RouterLink v-if="r.lead" to="/leads" class="text-brand-600">{{
							$t("Open leads")
						}}</RouterLink></template
					>
				</div>
			</article>
		</div>
		<section v-if="schedules.length" class="card p-5">
			<h2 class="mb-3 text-xl font-semibold">{{ $t("Schedules") }}</h2>
			<div
				v-for="s in schedules"
				:key="s.name"
				class="flex items-center justify-between gap-4 border-t border-slate-100 py-3"
			>
				<div>
					<p class="font-medium">{{ s.title }}</p>
					<p class="text-sm text-slate-500">
						{{ s.property }} · {{ $t(s.frequency) }} · {{ $t("Next due") }}
						{{ s.next_due }} · {{ $t(s.active ? "Active" : "Paused") }}
					</p>
				</div>
				<Button v-if="manager" @click="edit(s)">{{ $t("Edit") }}</Button>
			</div>
		</section>
		<EditForm
			v-if="dialog"
			:key="dialog.id"
			v-bind="dialog"
			@close="dialog = null"
			@saved="saved"
		/>
	</div>
</template>
<script setup>
import { computed, ref, watch } from "vue";
import { post } from "@/api";
import { ui, boot } from "@/store";
import Button from "@/components/Button.vue";
import EditForm from "./EditForm.vue";
import { read, write, upload, download, title as label } from "./shared";
const props = defineProps({ kind: String });
const configs = {
	workorders: {
		title: "Maintenance",
		hint: "Review quotes, assign repairs, and record completion evidence before paying.",
		create: "New work order",
		read: "workorders.list_orders",
		save: "workorders.save_order",
		doctype: "Rent Work Order",
		details: [
			"room",
			"assigned_to",
			"due_date",
			"quote_amount",
			"actual_cost",
			"description",
			"quote_note",
			"completion_note",
			"expense",
		],
	},
	recurring: {
		title: "Recurring bills",
		hint: "Schedules create unpaid bills. Record payment separately to add an expense.",
		create: "New bill schedule",
		read: "recurring.overview",
		save: "recurring.save_schedule",
		doctype: "Rent Operating Bill",
		details: ["due_date", "category", "amount", "notes", "expense"],
	},
	housekeeping: {
		title: "Housekeeping",
		hint: "Daily routines, clear assignments, and evidence of completed work.",
		create: "New cleaning schedule",
		read: "housekeeping.overview",
		save: "housekeeping.save_schedule",
		doctype: "Rent Housekeeping Task",
		details: ["room", "assigned_to", "due_date", "notes"],
	},
	waitlist: {
		title: "Waitlist",
		hint: "Match current vacancies by budget and room type. Offers are tentative: no bed is held until normal booking. Future move-in availability must be confirmed.",
		create: "Add to waitlist",
		read: "waitlist.overview",
		save: "waitlist.save_entry",
		doctype: "Rent Waitlist",
		details: [
			"phone",
			"email",
			"room_type",
			"budget",
			"move_in_date",
			"offer_room",
			"offer_expires",
			"notes",
		],
	},
};
const config = computed(() => configs[props.kind]);
const rows = ref([]),
	schedules = ref([]),
	options = ref({}),
	extra = ref({}),
	busy = ref(false),
	error = ref(""),
	notice = ref(""),
	search = ref(""),
	filter = ref(""),
	dialog = ref(null),
	checks = ref({});
let version = 0;
const manager = computed(() => !boot.access);
const statuses = computed(() => [...new Set(rows.value.map((r) => r.status))]);
const filtered = computed(() =>
	rows.value.filter(
		(r) =>
			(!filter.value || r.status === filter.value) &&
			[r.subject, r.title, r.full_name, r.property, r.name]
				.join(" ")
				.toLowerCase()
				.includes(search.value.toLowerCase()),
	),
);
const today = new Date().toLocaleDateString("en-CA");
const overdue = (r) =>
	r.due_date &&
	r.due_date < today &&
	["Due", "Open", "Approved", "In Progress"].includes(r.status);
const checklist = (r) => {
	try {
		return JSON.parse(r.checklist || "[]");
	} catch {
		return [];
	}
};
const canUpload = (r) =>
	(manager.value || r.assigned_to === boot.user) &&
	["Draft", "Approved", "In Progress", "Open"].includes(r.status);
async function load() {
	const v = ++version;
	busy.value = true;
	error.value = "";
	try {
		const key = {
			workorders: "requests",
			recurring: "expenses",
			housekeeping: "housekeeping",
			waitlist: "leads",
		}[props.kind];
		const [data, opts] = await Promise.all([
			read(config.value.read, { property: ui.property }),
			read("catalog.options", { key }),
		]);
		if (v !== version) return;
		extra.value = data;
		options.value = opts;
		rows.value = Array.isArray(data) ? data : data.bills || data.tasks || [];
		schedules.value = data.schedules || [];
		checks.value = Object.fromEntries(
			rows.value.map((r) => [r.name, checklist(r).flatMap((x, i) => (x.done ? [i] : []))]),
		);
	} catch (e) {
		if (v === version) error.value = e.message;
	} finally {
		if (v === version) busy.value = false;
	}
}
watch(
	() => [props.kind, ui.property],
	() => {
		filter.value = "";
		search.value = "";
		load();
	},
	{ immediate: true },
);
async function run(name, args = {}) {
	if (busy.value) return;
	busy.value = true;
	error.value = "";
	try {
		await write(name, args);
		notice.value = "Saved";
		await load();
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
function open(title, fields, initial, save, hint) {
	dialog.value = { id: Date.now(), title, fields, initial, save, hint };
}
async function saved(result) {
	dialog.value = null;
	notice.value = result?.approval_pending ? "Submitted for approval" : "Saved";
	await load();
}
const f = (key, type = "text", required = false, opts) => ({
	key,
	type,
	required,
	...(opts ? { options: opts } : {}),
});
function edit(row = {}) {
	const opts = options.value;
	const properties = (opts.properties || []).map((p) => ({
		value: p.name,
		label: p.property_name || p.name,
	}));
	let fields = [
		f(
			props.kind === "workorders"
				? "subject"
				: props.kind === "waitlist"
					? "full_name"
					: "title",
			"text",
			true,
		),
		f("property", "text", true, properties),
	];
	const users = (opts.users || []).map((u) => ({
		value: u.name,
		label: `${u.full_name} (${u.name})`,
	}));
	const rooms = (opts.rooms || []).map((r) => ({
		value: r.name,
		label: `${r.property} / ${r.room_number}`,
	}));
	const vendors = (opts.vendors || []).map((v) => ({ value: v.name, label: v.vendor_name }));
	if (props.kind === "workorders")
		fields.push(
			f("room", "text", false, rooms),
			f(
				"request",
				"text",
				false,
				(opts.requests || []).map((r) => ({
					value: r.name,
					label: `${r.property}: ${r.subject}`,
				})),
			),
			f("vendor", "text", false, vendors),
			f("assigned_to", "text", true, users),
			f("due_date", "date", true),
			f("quote_amount", "number", true),
			f("description", "textarea"),
			f("quote_note", "textarea"),
		);
	if (props.kind === "recurring")
		fields.push(
			f("vendor", "text", false, vendors),
			f("category", "text", true, extra.value.categories || []),
			f("amount", "number", true),
			f("frequency", "text", true, ["Weekly", "Monthly", "Quarterly", "Yearly"]),
			{ ...f("start_date", "date", true), disabled: !!row.name },
			f("end_date", "date"),
			f("active", "checkbox"),
			f("notes", "textarea"),
		);
	if (props.kind === "housekeeping")
		fields.push(
			f("room", "text", false, rooms),
			f("assigned_to", "text", true, users),
			f("frequency", "text", true, ["Daily", "Weekly", "Monthly"]),
			{ ...f("start_date", "date", true), disabled: !!row.name },
			f("active", "checkbox"),
			f("require_photo", "checkbox"),
			f("checklist", "textarea", true),
		);
	if (props.kind === "waitlist")
		fields.push(
			f("phone", "tel", true),
			f("email", "email"),
			f("room_type", "text", false, [
				...new Set((opts.rooms || []).map((r) => r.room_type).filter(Boolean)),
			]),
			f("budget", "number", true),
			f("move_in_date", "date", true),
			f("notes", "textarea"),
		);
	open(
		row.name ? "Edit" : config.value.create,
		fields,
		{
			active: 1,
			require_photo: 1,
			frequency: props.kind === "housekeeping" ? "Daily" : "Monthly",
			property: ui.property || properties[0]?.value,
			start_date: today,
			...row,
		},
		(data) => write(config.value.save, { data }),
		props.kind === "housekeeping" ? "Enter one checklist item per line." : undefined,
	);
}
function vendor() {
	open(
		"Add vendor",
		[
			f("vendor_name", "text", true),
			f("phone", "tel"),
			f("email", "email"),
			f("speciality"),
			f("is_active", "checkbox"),
		],
		{ is_active: 1 },
		(data) => write("workorders.save_vendor", { data }),
	);
}
function orderActions(r) {
	if (manager.value) {
		const map = {
			Draft: ["request", "cancel"],
			"Pending Approval":
				r.requested_by === boot.user ? ["cancel"] : ["approve", "reject", "cancel"],
			Approved: ["start", "cancel"],
			"In Progress": ["complete"],
		};
		return map[r.status] || [];
	}
	return r.assigned_to === boot.user
		? { Approved: ["start"], "In Progress": ["complete"] }[r.status] || []
		: [];
}
function orderAction(r, action) {
	if (["complete", "reject"].includes(action)) {
		const fields = [f("note", "textarea", true)];
		if (action === "complete")
			fields.push({ ...f("actual_cost", "number", true), min: 0, max: r.quote_amount });
		open(label(action), fields, { actual_cost: r.quote_amount }, (data) =>
			write("workorders.transition", { name: r.name, action, ...data }),
		);
	} else run("workorders.transition", { name: r.name, action });
}
function payment(r, method) {
	open(
		"Record payment",
		[
			f("mode_of_payment", "text", true, ["Cash", "Bank Transfer", "UPI", "Cheque"]),
			f("reference_no"),
		],
		{ mode_of_payment: "Bank Transfer" },
		(data) => post(method, { name: r.name, ...data }),
		"Record a payment only after it has actually been made. Approval rules still apply.",
	);
}
function reason(title, method, r, key) {
	open(title, [f(key, "textarea", true)], {}, (data) => write(method, { name: r.name, ...data }));
}
function finishTask(r) {
	open("Complete", [f("notes", "textarea")], {}, (data) =>
		write("housekeeping.update_task", {
			name: r.name,
			action: "complete",
			checked: [...(checks.value[r.name] || [])].sort((a, b) => a - b),
			...data,
		}),
	);
}
async function attach(r, field, event) {
	busy.value = true;
	error.value = "";
	try {
		await upload(config.value.doctype, r.name, field, event.target.files[0]);
		await load();
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
		event.target.value = "";
	}
}
async function match(r) {
	busy.value = true;
	error.value = "";
	try {
		const matches = await read("waitlist.matches", { name: r.name });
		if (!matches.length) {
			notice.value = "No matching vacancies right now.";
			return;
		}
		open(
			"Create tentative offer",
			[
				f(
					"room",
					"text",
					true,
					matches.map((m) => ({
						value: m.name,
						label: `${m.room_number} · ${m.room_type} · ${m.room_rent} · ${m.free_beds} free`,
					})),
				),
				{ ...f("expires_in_days", "number", true), min: 1, max: 14 },
			],
			{ expires_in_days: 2 },
			(data) => write("waitlist.offer", { name: r.name, ...data }),
			"This offer does not reserve a bed or send a message. Contact the applicant separately.",
		);
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
</script>
