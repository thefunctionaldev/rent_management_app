<template>
	<div class="p-5">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<p class="text-sm text-slate-500">{{ intro }}</p>
			<Button size="sm" :icon="Plus" @click="editing = blank()">Add a document</Button>
		</div>
		<Skeleton v-if="!data" class="mt-4 h-24" />
		<p v-else-if="!data.documents.length" class="mt-4 text-sm text-slate-500">
			No documents yet.
		</p>
		<ul v-else class="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200">
			<li
				v-for="d in data.documents"
				:key="d.key"
				class="flex items-center gap-3 px-4 py-3 text-sm"
			>
				<span
					class="grid size-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-500"
				>
					<FileText v-if="d.is_pdf" class="size-4" />
					<ImageIcon v-else class="size-4" />
				</span>
				<div class="min-w-0 flex-1">
					<p class="font-medium">
						{{ d.document_type }}
						<span v-if="d.document_number" class="font-normal text-slate-500"
							>· {{ d.document_number }}</span
						>
					</p>
					<p class="text-xs text-slate-500">
						<template v-if="d.expires_on">
							<span
								:class="
									d.expired
										? 'font-medium text-rose-600'
										: d.expiring
										? 'font-medium text-amber-700'
										: ''
								"
								>{{ d.expired ? "Expired" : "Expires" }}
								{{ date(d.expires_on) }}</span
							>
							·
						</template>
						<template v-if="d.note">{{ d.note }} · </template>
						{{
							d.source === "Tenant App"
								? tenantApp
									? "Added by you"
									: "Added by the tenant"
								: d.source === "Manager"
								? tenantApp
									? "Added by your landlord"
									: "Added here"
								: `From ${d.source.toLowerCase()}`
						}}
					</p>
				</div>
				<a :href="fileUrl(d)" target="_blank" class="text-brand-600 hover:underline"
					>Open</a
				>
				<template v-if="canEdit(d)">
					<button
						class="text-slate-400 hover:text-slate-700"
						title="Edit"
						@click="editing = { ...d, upload: '' }"
					>
						<Pencil class="size-4" />
					</button>
					<button
						class="text-slate-400 hover:text-rose-600"
						title="Delete"
						@click="remove(d)"
					>
						<Trash2 class="size-4" />
					</button>
				</template>
			</li>
		</ul>

		<Modal
			:open="!!editing"
			:title="editing?.name ? 'Edit document' : 'Add a document'"
			@close="editing = null"
		>
			<form v-if="editing" id="document-form" class="space-y-4" @submit.prevent="save">
				<div class="grid gap-4 sm:grid-cols-2">
					<Field label="Document">
						<select v-model="editing.document_type" class="input" required>
							<option v-for="t in data.types" :key="t">{{ t }}</option>
						</select>
					</Field>
					<Field
						:label="
							editing.document_type === 'Aadhaar Card' ? 'Last 4 digits' : 'Number'
						"
					>
						<input v-model="editing.document_number" class="input" />
					</Field>
					<Field label="Issued on">
						<input v-model="editing.issued_on" type="date" class="input" />
					</Field>
					<Field label="Expires on" hint="Reminder 30 days before">
						<input v-model="editing.expires_on" type="date" class="input" />
					</Field>
				</div>
				<FileInput v-model="editing.upload" :current="editing.file || ''" />
				<Field label="Note">
					<input v-model="editing.note" class="input" />
				</Field>
			</form>
			<template #footer>
				<Button @click="editing = null">Cancel</Button>
				<Button variant="primary" type="submit" form="document-form" :loading="busy"
					>Save</Button
				>
			</template>
		</Modal>
	</div>
</template>

<script setup>
import { FileText, Image as ImageIcon, Pencil, Plus, Trash2 } from "lucide-vue-next";
import { ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import FileInput from "@/components/FileInput.vue";
import Modal from "@/components/Modal.vue";
import Skeleton from "@/components/Skeleton.vue";
import { toast } from "@/store";
import { date } from "@/utils";

// for a manager (tenant given) or the tenant themselves (tenantApp)
const props = defineProps({
	tenant: { type: [String, Number], default: null },
	tenantApp: Boolean,
	intro: {
		type: String,
		default: "ID, PAN, visa, offer letter… with reminders before they expire.",
	},
});

const PORTAL = "rent_management.portal.";
const data = ref(null);
async function load() {
	data.value = props.tenantApp
		? await get(`${PORTAL}get_documents`)
		: await get("get_tenant_documents", { tenant: props.tenant });
}
load();

const canEdit = (d) => d.editable && (!props.tenantApp || d.source === "Tenant App");
const fileUrl = (d) =>
	props.tenantApp
		? `/api/method/${PORTAL}document_file?key=${encodeURIComponent(d.key)}`
		: d.file;
const blank = () => ({
	document_type: "PAN Card",
	document_number: "",
	issued_on: "",
	expires_on: "",
	note: "",
	upload: "",
});

const editing = ref(null);
const busy = ref(false);
async function save() {
	busy.value = true;
	const doc = { ...editing.value, upload: editing.value.upload || null };
	try {
		if (props.tenantApp) data.value = await post(`${PORTAL}save_document`, { data: doc });
		else {
			await post("save_tenant_document", { tenant: props.tenant, data: doc });
			await load();
		}
		toast("Document saved");
		editing.value = null;
	} catch (e) {
		toast(e.message, "error");
	} finally {
		busy.value = false;
	}
}
async function remove(d) {
	if (!confirm(`Delete the ${d.document_type}?`)) return;
	try {
		if (props.tenantApp) data.value = await post(`${PORTAL}delete_document`, { name: d.key });
		else {
			await post("delete_tenant_document", { tenant: props.tenant, name: d.key });
			await load();
		}
		toast("Document deleted");
	} catch (e) {
		toast(e.message, "error");
	}
}
</script>
