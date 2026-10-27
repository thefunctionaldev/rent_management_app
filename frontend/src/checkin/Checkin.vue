<template>
	<div class="min-h-screen bg-slate-50 pb-16 text-slate-900">
		<div v-if="loading" class="grid min-h-screen place-items-center">
			<div
				class="size-8 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600"
			/>
		</div>
		<div v-else-if="error" class="grid min-h-screen place-items-center px-6 text-center">
			<div>
				<p class="text-lg font-semibold">This link doesn't work</p>
				<p class="mt-1 text-sm text-slate-500">{{ error }}</p>
			</div>
		</div>

		<template v-else>
			<header
				class="bg-gradient-to-br from-brand-700 via-brand-600 to-violet-600 text-white"
			>
				<div class="mx-auto max-w-2xl px-5 pt-8 pb-20">
					<p class="text-sm text-white/70">
						{{ data.stay.building }} · Room {{ data.stay.room }}
					</p>
					<h1 class="mt-1 text-2xl font-semibold tracking-tight">
						{{ done ? "You're checked in" : `Welcome, ${data.tenant.first_name}!` }}
					</h1>
					<p class="mt-1 text-sm text-white/80">
						{{
							done
								? "Your details are saved and your agreement is signed."
								: "Three short steps to finish your check-in. About 5 minutes."
						}}
					</p>
					<ol v-if="!done" class="mt-6 grid grid-cols-3 gap-2 text-xs">
						<li
							v-for="(label, i) in steps"
							:key="label"
							class="rounded-full px-3 py-1.5 text-center font-medium"
							:class="
								i < step
									? 'bg-white/90 text-brand-700'
									: i === step
									? 'bg-white text-brand-700 ring-2 ring-white/50'
									: 'bg-white/15 text-white/80'
							"
						>
							{{ i < step ? "✓ " : `${i + 1}. ` }}{{ label }}
						</li>
					</ol>
				</div>
			</header>

			<main class="mx-auto -mt-12 max-w-2xl space-y-4 px-4">
				<!-- 1: details -->
				<form v-if="step === 0" class="card space-y-4 p-5" @submit.prevent="step = 1">
					<h2 class="font-semibold">Your details</h2>
					<div class="grid gap-3 sm:grid-cols-3">
						<Field label="First name" required>
							<input v-model="form.first_name" class="input" required />
						</Field>
						<Field label="Middle name">
							<input v-model="form.middle_name" class="input" />
						</Field>
						<Field label="Last name">
							<input v-model="form.last_name" class="input" />
						</Field>
					</div>
					<div class="grid gap-3 sm:grid-cols-2">
						<Field label="Gender" required>
							<select v-model="form.gender" class="input" required>
								<option value="" disabled>Choose</option>
								<option>Male</option>
								<option>Female</option>
								<option>Other</option>
							</select>
						</Field>
						<Field label="Date of birth" required>
							<input
								v-model="form.date_of_birth"
								class="input"
								type="date"
								required
							/>
						</Field>
						<Field label="Father's / guardian's name" required>
							<input v-model="form.guardian_name" class="input" required />
						</Field>
						<Field label="Email">
							<input v-model="form.email_id" class="input" type="email" />
						</Field>
					</div>
					<Field label="Permanent address" required hint="As on your ID">
						<textarea
							v-model="form.permanent_address"
							class="input"
							rows="2"
							required
						/>
					</Field>
					<div class="grid gap-3 sm:grid-cols-3">
						<Field label="Occupation">
							<input
								v-model="form.occupation"
								class="input"
								placeholder="Student, engineer..."
							/>
						</Field>
						<Field label="Company / college">
							<input v-model="form.workspace" class="input" />
						</Field>
						<Field label="Monthly income">
							<input
								v-model="form.salary"
								class="input tabular"
								type="number"
								min="0"
							/>
						</Field>
					</div>
					<h3 class="pt-2 text-sm font-semibold">Emergency contact</h3>
					<div class="grid gap-3 sm:grid-cols-3">
						<Field label="Name" required>
							<input v-model="form.emergency_contact_name" class="input" required />
						</Field>
						<Field label="Relation">
							<input
								v-model="form.emergency_contact_relation"
								class="input"
								placeholder="Father, sister..."
							/>
						</Field>
						<Field label="Phone" required>
							<input
								v-model="form.emergency_contact_phone"
								class="input"
								type="tel"
								required
							/>
						</Field>
					</div>
					<Button variant="primary" size="lg" type="submit" class="w-full">Next</Button>
				</form>

				<!-- 2: ID and photo -->
				<form
					v-else-if="step === 1"
					class="card space-y-5 p-5"
					@submit.prevent="saveDetails"
				>
					<h2 class="font-semibold">Your ID and photo</h2>
					<p class="text-sm text-slate-500">
						Needed for your stay and for police verification. Only your landlord can
						see them.
					</p>
					<Field
						label="Aadhaar number"
						:required="!data.tenant.aadhaar_last4"
						:hint="
							data.tenant.aadhaar_last4
								? `Saved (•••• ${data.tenant.aadhaar_last4}). Leave blank to keep it.`
								: '12 digits'
						"
					>
						<input
							v-model="aadhaar"
							class="input tabular"
							inputmode="numeric"
							autocomplete="off"
							:required="!data.tenant.aadhaar_last4"
							placeholder="1234 5678 9012"
						/>
					</Field>
					<div>
						<p class="label">
							Photo of your Aadhaar card
							<span v-if="data.has_aadhaar_card" class="font-normal text-emerald-600"
								>· saved</span
							>
						</p>
						<PictureInput v-model="aadhaarCard" name="Aadhaar card" />
					</div>
					<div>
						<p class="label">
							Your photo
							<span v-if="data.has_photo" class="font-normal text-emerald-600"
								>· saved</span
							>
						</p>
						<PictureInput v-model="photo" round :name="fullName" />
					</div>
					<p v-if="formError" class="text-sm text-rose-600">{{ formError }}</p>
					<div class="flex gap-3">
						<Button size="lg" @click="step = 0">Back</Button>
						<Button
							variant="primary"
							size="lg"
							type="submit"
							class="flex-1"
							:loading="saving"
							>Save and continue</Button
						>
					</div>
				</form>

				<!-- 3: agreement -->
				<div v-else-if="step === 2 && !done" class="card space-y-4 p-5">
					<h2 class="font-semibold">Read and sign your rental agreement</h2>
					<iframe
						:srcdoc="agreementPage"
						sandbox=""
						title="Rental agreement"
						class="h-[60vh] w-full rounded-xl border border-slate-200 bg-white"
					/>
					<Field
						label="Type your full name to sign"
						required
						:hint="`As above: ${fullName}`"
					>
						<input v-model="signName" class="input" autocomplete="name" />
					</Field>
					<label class="flex items-start gap-3 text-sm">
						<input
							v-model="agree"
							type="checkbox"
							class="mt-0.5 size-4 accent-brand-600"
						/>
						<span
							>I have read this agreement and agree to it. I understand that signing
							here is the same as signing on paper.</span
						>
					</label>
					<template v-if="data.code_channel">
						<div class="flex flex-wrap items-end gap-3">
							<Field label="Code" class="w-40">
								<input
									v-model="code"
									class="input tabular tracking-widest"
									inputmode="numeric"
									maxlength="6"
									placeholder="••••••"
								/>
							</Field>
							<Button :loading="sending" :disabled="!canAsk" @click="sendCode">{{
								codeSentTo ? "Send again" : "Send me a code"
							}}</Button>
						</div>
						<p class="text-xs text-slate-500">
							<template v-if="codeSentTo"
								>We sent a code by {{ data.code_channel }} to
								{{ codeSentTo }}.</template
							>
							<template v-else
								>We'll send a code by {{ data.code_channel }} to
								{{ data.code_sent_to }} to confirm it's you.</template
							>
						</p>
					</template>
					<p v-if="formError" class="text-sm text-rose-600">{{ formError }}</p>
					<div class="flex gap-3">
						<Button size="lg" @click="step = 1">Back</Button>
						<Button
							variant="primary"
							size="lg"
							class="flex-1"
							:icon="PenLine"
							:loading="signing"
							:disabled="!canSign"
							@click="signAgreement"
							>Sign agreement</Button
						>
					</div>
				</div>

				<!-- done -->
				<div v-if="done" class="card p-6">
					<div class="flex items-start gap-3">
						<span
							class="grid size-11 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-600"
							><CircleCheck class="size-6"
						/></span>
						<div>
							<p class="font-semibold">Signed by {{ data.signed_name }}</p>
							<p class="text-sm text-slate-500">{{ when(data.signed_on) }}</p>
							<p class="mt-3 text-sm text-slate-600">
								Your landlord has your details and the signed agreement. You can
								download it any time from the tenant app.
							</p>
						</div>
					</div>
					<iframe
						:srcdoc="agreementPage"
						sandbox=""
						title="Rental agreement"
						class="mt-5 h-[50vh] w-full rounded-xl border border-slate-200 bg-white"
					/>
				</div>

				<p v-if="data.landlord.phone" class="text-center text-sm text-slate-500">
					Questions? Call {{ data.landlord.name || "your landlord" }} on
					<a :href="`tel:${data.landlord.phone}`" class="font-medium text-brand-700">{{
						data.landlord.phone
					}}</a>
				</p>
			</main>
		</template>
	</div>
</template>

<script setup>
import { CircleCheck, PenLine } from "lucide-vue-next";
import { computed, onMounted, reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import PictureInput from "@/components/PictureInput.vue";

const METHOD = "rent_management.checkin.";
const key = new URLSearchParams(window.location.search).get("key");
const steps = ["Details", "ID & photo", "Sign"];

const loading = ref(true);
const error = ref("");
const data = ref(null);
const step = ref(0);
const done = computed(() => data.value?.status === "Signed");

const form = reactive({
	first_name: "",
	middle_name: "",
	last_name: "",
	gender: "",
	date_of_birth: "",
	guardian_name: "",
	email_id: "",
	permanent_address: "",
	occupation: "",
	workspace: "",
	salary: "",
	emergency_contact_name: "",
	emergency_contact_relation: "",
	emergency_contact_phone: "",
});
const fullName = computed(() =>
	[form.first_name, form.middle_name, form.last_name].filter(Boolean).join(" ")
);
const aadhaar = ref("");
const aadhaarCard = ref("");
const photo = ref("");

const agreementPage = computed(
	() =>
		`<!doctype html><html><head><meta charset="utf-8"><style>body{margin:16px;font-family:system-ui,sans-serif}</style></head><body>${
			data.value?.agreement || ""
		}</body></html>`
);

function apply(result) {
	data.value = result;
	for (const field of Object.keys(form)) form[field] = result.tenant[field] ?? "";
}

const formError = ref("");
const saving = ref(false);
async function saveDetails() {
	saving.value = true;
	formError.value = "";
	try {
		apply(
			await post(METHOD + "save_details", {
				key,
				details: { ...form },
				aadhaar_number: aadhaar.value || null,
				// only new pictures (data URLs) are sent
				aadhaar_card: aadhaarCard.value.startsWith("data:") ? aadhaarCard.value : null,
				photo: photo.value.startsWith("data:") ? photo.value : null,
			})
		);
		aadhaar.value = "";
		step.value = 2;
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) {
		formError.value = e.message;
	} finally {
		saving.value = false;
	}
}

const signName = ref("");
const agree = ref(false);
const code = ref("");
const codeSentTo = ref("");
const sending = ref(false);
const canAsk = computed(() => !sending.value);
const canSign = computed(
	() =>
		signName.value.trim() &&
		agree.value &&
		(!data.value?.code_channel || code.value.length === 6)
);

async function sendCode() {
	sending.value = true;
	formError.value = "";
	try {
		const result = await post(METHOD + "send_code", { key });
		codeSentTo.value = result.sent_to || "";
	} catch (e) {
		formError.value = e.message;
	} finally {
		sending.value = false;
	}
}

const signing = ref(false);
async function signAgreement() {
	signing.value = true;
	formError.value = "";
	try {
		apply(
			await post(METHOD + "sign", {
				key,
				name: signName.value,
				agree: agree.value ? 1 : 0,
				code: code.value,
			})
		);
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) {
		formError.value = e.message;
	} finally {
		signing.value = false;
	}
}

function when(value) {
	return value
		? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(
				new Date(value.replace(" ", "T"))
		  )
		: "";
}

onMounted(async () => {
	try {
		apply(await get(METHOD + "get_checkin", { key }));
		step.value = data.value.status === "Details Submitted" ? 2 : 0;
	} catch (e) {
		error.value = e.message;
	} finally {
		loading.value = false;
	}
});
</script>
