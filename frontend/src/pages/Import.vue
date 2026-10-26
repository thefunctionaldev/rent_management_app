<template>
	<div>
		<PageHeader
			title="Import from Excel"
			subtitle="Bring in the rooms and tenants you already track in a spreadsheet"
		/>

		<div class="mb-6 grid gap-4 md:grid-cols-2">
			<button
				v-for="k in kinds"
				:key="k.value"
				class="card flex items-start gap-4 p-5 text-left transition"
				:class="kind === k.value ? 'ring-2 ring-brand-500' : 'hover:bg-slate-50'"
				@click="choose(k.value)"
			>
				<span
					class="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600"
				>
					<component :is="k.icon" class="size-5" />
				</span>
				<div>
					<p class="font-semibold">{{ k.label }}</p>
					<p class="mt-0.5 text-sm text-slate-500">{{ k.description }}</p>
				</div>
			</button>
		</div>

		<div class="card p-6">
			<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<p class="font-semibold">1. Fill in the template</p>
					<p class="text-sm text-slate-500">
						Your own sheet works too if its first row has the same column names.
						{{ kind === "tenants" ? "Import rooms first if tenants have rooms." : "" }}
					</p>
				</div>
				<Button :icon="Download" :href="templateUrl">Download template</Button>
			</div>

			<div class="my-6 border-t border-dashed border-slate-200" />

			<p class="font-semibold">2. Upload it</p>
			<label
				class="mt-3 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 px-6 py-10 text-center transition hover:border-brand-400 hover:bg-brand-50/40"
				:class="dragging && 'border-brand-500 bg-brand-50/60'"
				@dragover.prevent="dragging = true"
				@dragleave="dragging = false"
				@drop.prevent="onDrop"
			>
				<FileSpreadsheet class="size-8 text-slate-400" />
				<p class="mt-2 text-sm font-medium text-slate-700">
					{{ file ? file.name : "Drop an .xlsx or .csv file here, or click to choose" }}
				</p>
				<p v-if="file" class="text-xs text-slate-500">Click to choose another file</p>
				<input type="file" accept=".xlsx,.csv" class="hidden" @change="onPick" />
			</label>

			<div v-if="checking" class="mt-6 flex items-center gap-3 text-sm text-slate-500">
				<span
					class="size-4 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600"
				/>
				Checking every row…
			</div>

			<template v-if="result">
				<div class="my-6 border-t border-dashed border-slate-200" />
				<div
					class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
				>
					<div>
						<p class="font-semibold">
							{{ result.dry_run ? "3. Check and import" : "Done" }}
						</p>
						<p class="text-sm text-slate-500">
							<span class="font-medium text-emerald-700"
								>{{ result.ok }} row{{ result.ok === 1 ? "" : "s" }}
								{{ result.dry_run ? "ready" : "imported" }}</span
							>
							<template v-if="result.errors">
								·
								<span class="font-medium text-rose-700"
									>{{ result.errors }} with problems</span
								>
								{{
									result.dry_run
										? "(fix them in the file and upload again, or import the rest)"
										: "(skipped)"
								}}
							</template>
						</p>
					</div>
					<Button
						v-if="result.dry_run"
						variant="primary"
						:icon="Upload"
						:loading="importing"
						:disabled="!result.ok"
						@click="runImport"
						>Import {{ result.ok }} row{{ result.ok === 1 ? "" : "s" }}</Button
					>
					<Button v-else variant="primary" :href="doneLink.href">{{
						doneLink.label
					}}</Button>
				</div>
				<div class="overflow-x-auto rounded-xl border border-slate-200">
					<table class="w-full">
						<thead class="border-b border-slate-100 bg-slate-50/60">
							<tr>
								<th class="table-head w-16">Row</th>
								<th class="table-head">
									{{ kind === "rooms" ? "Room" : "Tenant" }}
								</th>
								<th class="table-head">Result</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-slate-100">
							<tr v-for="r in result.rows" :key="r.row">
								<td class="table-cell tabular text-slate-500">{{ r.row }}</td>
								<td class="table-cell font-medium">{{ rowLabel(r) }}</td>
								<td class="table-cell whitespace-normal">
									<span
										class="inline-flex items-start gap-1.5 text-sm"
										:class="
											r.status === 'ok' ? 'text-slate-600' : 'text-rose-700'
										"
									>
										<CircleCheck
											v-if="r.status === 'ok'"
											class="mt-0.5 size-4 shrink-0 text-emerald-600"
										/>
										<CircleAlert v-else class="mt-0.5 size-4 shrink-0" />
										{{ r.message }}
									</span>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup>
import {
	CircleAlert,
	CircleCheck,
	DoorOpen,
	Download,
	FileSpreadsheet,
	Upload,
	Users,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import PageHeader from "@/components/PageHeader.vue";
import { bumpData, reloadProperties, toast } from "@/store";

const kinds = [
	{
		value: "rooms",
		label: "Rooms",
		icon: DoorOpen,
		description: "Building, room number, floor, beds, room type, rent and deposit.",
	},
	{
		value: "tenants",
		label: "Tenants",
		icon: Users,
		description: "Name and contact details, and optionally their room, move-in date and rent.",
	},
];
const kind = ref("rooms");
const file = ref(null);
const content = ref("");
const result = ref(null);
const checking = ref(false);
const importing = ref(false);
const dragging = ref(false);

const templateUrl = computed(
	() => `/api/method/rent_management.api.get_import_template?kind=${kind.value}`
);
const doneLink = computed(() =>
	kind.value === "rooms"
		? { href: "/rent/rooms", label: "View rooms" }
		: { href: "/rent/tenants", label: "View tenants" }
);

function choose(value) {
	kind.value = value;
	file.value = null;
	result.value = null;
}

function rowLabel(r) {
	const v = r.values;
	if (kind.value === "rooms")
		return [v.room_number, v.property].filter(Boolean).join(" · ") || "—";
	return [v.first_name, v.last_name].filter(Boolean).join(" ") || "—";
}

const onPick = (event) => load(event.target.files[0]);
const onDrop = (event) => {
	dragging.value = false;
	load(event.dataTransfer.files[0]);
};

function readFile(f) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(reader.result);
		reader.onerror = () => reject(new Error("Could not read the file"));
		reader.readAsDataURL(f);
	});
}

async function load(f) {
	if (!f) return;
	file.value = f;
	result.value = null;
	checking.value = true;
	try {
		content.value = await readFile(f);
		result.value = await send(1);
	} catch (e) {
		toast(e.message, "error");
	} finally {
		checking.value = false;
	}
}

const send = (dryRun) =>
	post("import_data", {
		kind: kind.value,
		filename: file.value.name,
		content: content.value,
		dry_run: dryRun,
	});

async function runImport() {
	importing.value = true;
	try {
		result.value = await send(0);
		toast(`${result.value.ok} ${kind.value} imported`);
		bumpData();
		reloadProperties();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		importing.value = false;
	}
}
</script>
