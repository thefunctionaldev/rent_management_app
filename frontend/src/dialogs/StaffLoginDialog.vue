<template>
	<Modal
		open
		:title="`App login for ${staff.staff_name}`"
		subtitle="What they can do in the manager app, on their phone"
		@close="$emit('close')"
	>
		<div v-if="link" class="space-y-4">
			<p class="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
				Done. {{ staff.staff_name.split(" ")[0] }} sets a password with this link, then
				logs in at <b>{{ appUrl }}</b> and adds it to the home screen.
			</p>
			<div class="flex gap-2">
				<input
					:value="link"
					class="input flex-1 text-xs"
					readonly
					@focus="$event.target.select()"
				/>
				<Button :icon="Copy" @click="copy">Copy</Button>
			</div>
			<Button
				v-if="staff.mobile_no"
				variant="success"
				class="w-full"
				:icon="MessageCircle"
				:href="whatsapp"
				target="_blank"
				>Send it on WhatsApp</Button
			>
		</div>
		<form v-else id="staff-login-form" class="space-y-4" @submit.prevent="save">
			<Field
				label="Their email"
				hint="They log in with it, and the link to set a password goes there"
			>
				<input v-model="form.email" type="email" class="input" required />
			</Field>
			<div>
				<div class="mb-2 flex items-center justify-between">
					<span class="label mb-0">They can use</span>
					<select class="input w-40 py-1 text-xs" @change="preset($event.target.value)">
						<option value="">Same as a…</option>
						<option
							v-for="(areas, name) in options?.presets || {}"
							:key="name"
							:value="name"
						>
							{{ name }}
						</option>
					</select>
				</div>
				<div class="grid gap-2 sm:grid-cols-2">
					<label
						v-for="a in options?.areas || []"
						:key="a.value"
						class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm ring-1 ring-slate-200"
						:class="form.areas.includes(a.value) && 'bg-brand-50 ring-brand-200'"
					>
						<input
							v-model="form.areas"
							type="checkbox"
							:value="a.value"
							class="size-4 accent-brand-600"
						/>
						{{ a.label }}
					</label>
				</div>
				<p class="mt-2 text-xs text-slate-500">
					Never: profit, the monthly report, salaries, settings, the subscription or
					Aadhaar numbers.
				</p>
			</div>
			<label class="flex items-center gap-2 text-sm text-slate-700">
				<input
					v-model="form.all_buildings"
					type="checkbox"
					class="size-4 accent-brand-600"
				/>
				All buildings (otherwise only {{ staff.property }})
			</label>
		</form>
		<template #footer>
			<template v-if="link">
				<Button variant="primary" @click="$emit('close')">Done</Button>
			</template>
			<template v-else>
				<Button
					v-if="staff.user"
					variant="ghost"
					class="sm:mr-auto"
					:loading="removing"
					@click="remove"
					>Remove login</Button
				>
				<Button @click="$emit('close')">Cancel</Button>
				<Button
					variant="primary"
					type="submit"
					form="staff-login-form"
					:loading="saving"
					>{{ staff.user ? "Save" : "Give login" }}</Button
				>
			</template>
		</template>
	</Modal>
</template>

<script setup>
import { Copy, MessageCircle } from "lucide-vue-next";
import { computed, reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { bumpData, toast } from "@/store";

const props = defineProps({ staff: { type: Object, required: true } });
const emit = defineEmits(["close"]);

const options = ref(null);
const form = reactive({
	email: props.staff.user || "",
	areas: (props.staff.app_areas || "").split(",").filter(Boolean),
	all_buildings: !!props.staff.app_all_buildings,
});
get("get_staff_access_options").then((result) => {
	options.value = result;
	if (!form.areas.length) preset(props.staff.role); // a cook gets the kitchen, a warden the register...
});
function preset(name) {
	const areas = options.value?.presets[name];
	if (areas) form.areas = [...areas];
}

const appUrl = `${window.location.origin}/rent`;
const link = ref("");
const whatsapp = computed(() => {
	const digits = (props.staff.mobile_no || "").replace(/[^\d]/g, "");
	const phone = digits.length === 10 ? `91${digits}` : digits;
	const text = `Hello ${
		props.staff.staff_name.split(" ")[0]
	}, here is your login to our PG app. Set your password: ${
		link.value
	} Then open ${appUrl} and add it to your home screen.`;
	return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
});

const saving = ref(false);
async function save() {
	saving.value = true;
	try {
		const result = await post("give_staff_login", {
			staff: props.staff.name,
			email: form.email,
			areas: form.areas,
			all_buildings: form.all_buildings ? 1 : 0,
		});
		bumpData();
		if (props.staff.user === result.user) {
			toast("Access updated");
			emit("close");
		} else {
			link.value = result.link;
		}
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = false;
	}
}

const removing = ref(false);
async function remove() {
	if (!confirm(`Remove ${props.staff.staff_name}'s login? They're logged out at once.`)) return;
	removing.value = true;
	try {
		await post("remove_staff_login", { staff: props.staff.name });
		toast("Login removed");
		bumpData();
		emit("close");
	} catch (e) {
		toast(e.message, "error");
	} finally {
		removing.value = false;
	}
}

async function copy() {
	try {
		await navigator.clipboard.writeText(link.value);
		toast("Link copied");
	} catch {
		toast("Couldn't copy, select the link instead", "error");
	}
}
</script>
