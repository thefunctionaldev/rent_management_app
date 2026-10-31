<template>
	<div>
		<PageHeader title="Settings" subtitle="Invoicing, online rent collection and reminders">
			<Button
				:icon="Download"
				href="/api/method/rent_management.api.export_data"
				title="Every building, room, tenant, invoice, payment and expense as an Excel file"
				>Download all data</Button
			>
			<Button
				variant="primary"
				:icon="Save"
				:loading="saving"
				:disabled="!form"
				@click="save"
				>Save changes</Button
			>
		</PageHeader>

		<div v-if="!form" class="space-y-4">
			<Skeleton v-for="i in 3" :key="i" class="h-48" />
		</div>

		<div v-else class="grid gap-6 lg:grid-cols-[1fr_22rem]">
			<div class="space-y-6">
				<!-- invoicing -->
				<section class="card p-6">
					<h2 class="font-semibold">Monthly invoicing</h2>
					<div class="mt-2 divide-y divide-slate-100">
						<Toggle
							v-model="form.auto_generate_invoices"
							label="Create rent invoices on the 1st of every month"
							hint="One invoice per tenant, pro-rated for move-ins and move-outs"
						/>
						<Toggle
							v-model="form.auto_submit_invoices"
							:disabled="!form.auto_generate_invoices"
							label="Submit them straight away"
							hint="Off: they are created as drafts for you to check first"
						/>
						<div class="flex items-center justify-between gap-4 py-3">
							<div>
								<p class="text-sm font-medium">Electricity rate per unit</p>
								<p class="text-xs text-slate-500">
									For rooms with their own meter
								</p>
							</div>
							<input
								v-model.number="form.electricity_rate"
								type="number"
								min="0"
								step="0.01"
								class="input tabular w-28"
							/>
						</div>
						<div class="flex items-center justify-between gap-4 py-3">
							<div>
								<p class="text-sm font-medium">Rent due day</p>
								<p class="text-xs text-slate-500">Day of the month rent is due</p>
							</div>
							<input
								v-model.number="form.rent_due_day"
								type="number"
								min="0"
								max="31"
								class="input tabular w-20"
							/>
						</div>
					</div>
				</section>

				<!-- late fees and discounts -->
				<section class="card p-6">
					<h2 class="font-semibold">Late fees and discounts</h2>
					<p class="mt-1 text-sm text-slate-500">
						Nudge tenants to pay on time. You can waive a late fee on any invoice.
					</p>
					<div class="mt-2 divide-y divide-slate-100">
						<Toggle
							v-model="form.late_fee_enabled"
							label="Charge a late fee"
							hint="Added to unpaid invoices once the grace days after the due date are over"
						/>
						<div v-if="form.late_fee_enabled" class="grid gap-3 py-3 sm:grid-cols-2">
							<Field label="Late fee">
								<select v-model="form.late_fee_type" class="input">
									<option value="Flat">A fixed amount, once</option>
									<option value="Per Day">An amount for every day late</option>
								</select>
							</Field>
							<Field
								:label="form.late_fee_type === 'Per Day' ? 'Per day' : 'Amount'"
							>
								<input
									v-model.number="form.late_fee_amount"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
							<Field label="Grace days" hint="after the due date">
								<input
									v-model.number="form.late_fee_grace_days"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
							<Field
								v-if="form.late_fee_type === 'Per Day'"
								label="At most"
								hint="empty: no limit"
							>
								<input
									v-model.number="form.late_fee_max"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
						</div>
						<Toggle
							v-model="form.early_discount_enabled"
							label="Discount for paying early"
							hint="Taken off when the invoice is paid in full by the date"
						/>
						<div
							v-if="form.early_discount_enabled"
							class="grid gap-3 py-3 sm:grid-cols-3"
						>
							<Field label="Discount">
								<select v-model="form.early_discount_type" class="input">
									<option value="Amount">An amount</option>
									<option value="Percent of Rent">A percent of the rent</option>
								</select>
							</Field>
							<Field
								:label="
									form.early_discount_type === 'Amount' ? 'Amount' : 'Percent'
								"
							>
								<input
									v-model.number="form.early_discount_value"
									type="number"
									min="0"
									step="0.5"
									class="input tabular"
								/>
							</Field>
							<Field label="Days before due" hint="0: by the due date">
								<input
									v-model.number="form.early_discount_days"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
						</div>
					</div>
				</section>

				<!-- owner's monthly summary -->
				<section class="card p-6">
					<h2 class="font-semibold">Monthly summary for the owner</h2>
					<p class="mt-1 text-sm text-slate-500">
						Collected, spent, profit, beds taken and who still owes, on WhatsApp and by
						email. See it any time under
						<RouterLink to="/summary" class="text-brand-600 hover:underline"
							>Monthly report</RouterLink
						>.
					</p>
					<div class="mt-2 divide-y divide-slate-100">
						<Toggle
							v-model="form.owner_summary_enabled"
							label="Send it every month"
							hint="Last month's summary, on the day you choose"
						/>
						<div
							v-if="form.owner_summary_enabled"
							class="grid gap-3 py-3 sm:grid-cols-3"
						>
							<Field label="On day">
								<input
									v-model.number="form.owner_summary_day"
									type="number"
									min="1"
									max="28"
									class="input tabular"
								/>
							</Field>
							<Field label="Owner's WhatsApp" hint="empty: landlord phone">
								<input
									v-model="form.owner_summary_phone"
									type="tel"
									class="input"
									:placeholder="form.landlord_phone"
								/>
							</Field>
							<Field label="Owner's email">
								<input
									v-model="form.owner_summary_email"
									type="email"
									class="input"
								/>
							</Field>
						</div>
					</div>
				</section>

				<!-- police verification -->
				<section class="card p-6">
					<h2 class="font-semibold">Police verification</h2>
					<p class="mt-1 text-sm text-slate-500">
						Track each new tenant's verification form until the police clear it. See it
						under
						<RouterLink to="/verification" class="text-brand-600 hover:underline"
							>Verification</RouterLink
						>.
					</p>
					<div class="mt-2 divide-y divide-slate-100">
						<Toggle
							v-model="form.police_verification_enabled"
							label="Track police verification"
							hint="New tenants start as to submit, with a reminder on the day it's due"
						/>
						<div
							v-if="form.police_verification_enabled"
							class="flex items-center justify-between gap-4 py-3"
						>
							<div>
								<p class="text-sm font-medium">Submit within</p>
								<p class="text-xs text-slate-500">Days after moving in</p>
							</div>
							<input
								v-model.number="form.police_verification_days"
								type="number"
								min="1"
								class="input tabular w-20"
							/>
						</div>
					</div>
				</section>

				<!-- referrals -->
				<section class="card p-6">
					<h2 class="font-semibold">Referrals</h2>
					<p class="mt-1 text-sm text-slate-500">
						Tenants share a link to your listing page from the tenant app. You follow
						referrals under Leads.
					</p>
					<div class="mt-2 divide-y divide-slate-100">
						<Toggle
							v-model="form.referrals_enabled"
							label="Reward tenants for referring friends"
							:hint="
								form.listing_enabled
									? 'Once the friend moves in and pays their first rent'
									: 'Needs the listing page (below) to be published'
							"
						/>
						<div v-if="form.referrals_enabled" class="grid gap-3 py-3 sm:grid-cols-2">
							<Field label="Reward" hint="off the referrer's next rent">
								<input
									v-model.number="form.referral_reward"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
							<Field label="Friend's discount" hint="off their first rent">
								<input
									v-model.number="form.referral_friend_discount"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
						</div>
					</div>
				</section>

				<!-- online collection -->
				<section class="card p-6">
					<h2 class="font-semibold">Online rent collection</h2>
					<p class="mt-1 text-sm text-slate-500">
						Rent goes straight to your own account. Nothing passes through us.
					</p>
					<div class="mt-4 grid gap-4 sm:grid-cols-2">
						<Field
							label="UPI ID"
							hint="A QR code for the exact amount is printed on every invoice"
						>
							<input
								v-model="form.upi_id"
								class="input"
								placeholder="yourname@okhdfcbank"
							/>
						</Field>
						<Field label="Name shown in UPI apps">
							<input
								v-model="form.upi_payee_name"
								class="input"
								placeholder="Sunrise PG"
							/>
						</Field>
					</div>
					<div class="mt-4 border-t border-slate-100">
						<Toggle
							v-model="form.razorpay_enabled"
							label="Payment links with Razorpay"
							hint="Tenants pay by UPI, card or netbanking and payments are recorded automatically"
						/>
					</div>
					<div v-if="form.razorpay_enabled" class="grid gap-4 sm:grid-cols-2">
						<Field label="Razorpay Key ID" required>
							<input
								v-model="form.razorpay_key_id"
								class="input"
								placeholder="rzp_live_..."
							/>
						</Field>
						<SecretField
							v-model="secrets.razorpay_key_secret"
							label="Razorpay Key Secret"
							:saved="form.razorpay_key_secret_set"
						/>
						<SecretField
							v-model="secrets.razorpay_webhook_secret"
							label="Webhook secret (optional)"
							:saved="form.razorpay_webhook_secret_set"
						/>
						<div class="text-xs text-slate-500 sm:pt-6">
							In Razorpay add a webhook for <b>payment_link.paid</b> to
							<code class="break-all text-slate-700">{{ data.webhook_url }}</code>
						</div>
					</div>
				</section>

				<!-- agreements -->
				<section class="card p-6">
					<h2 class="font-semibold">Listing page and bookings</h2>
					<p class="mt-1 text-sm text-slate-500">
						A page with your buildings' photos, rooms, prices and free beds. People
						enquire, book a visit or hold a bed with a token, and you follow them up in
						Leads.
					</p>
					<div class="mt-2 divide-y divide-slate-100">
						<Toggle
							v-model="form.listing_enabled"
							label="Publish the listing page"
							hint="Describe each building and add its photo under Buildings"
						/>
						<div
							v-if="form.listing_enabled"
							class="flex items-center justify-between gap-4 py-3"
						>
							<div>
								<p class="text-sm font-medium">Token to hold a bed</p>
								<p class="text-xs text-slate-500">
									Paid to you by UPI or Razorpay (above). 0: enquiries only.
								</p>
							</div>
							<input
								v-model.number="form.booking_token_amount"
								type="number"
								min="0"
								class="input tabular w-32"
							/>
						</div>
					</div>
					<p
						v-if="form.listing_enabled && data.listing_url"
						class="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500"
					>
						Your page:
						<a
							:href="data.listing_url"
							target="_blank"
							class="font-medium break-all text-brand-700"
							>{{ data.listing_url }}</a
						>
					</p>
				</section>

				<section class="card p-6">
					<h2 class="font-semibold">Rental agreements</h2>
					<p class="mt-1 text-sm text-slate-500">
						Printed for every tenant from their profile. Check it suits your state's
						rules.
					</p>
					<div class="mt-4 grid gap-4 sm:grid-cols-2">
						<Field label="Landlord / owner name">
							<input v-model="form.landlord_name" class="input" />
						</Field>
						<Field label="Landlord phone">
							<input v-model="form.landlord_phone" class="input" />
						</Field>
						<Field label="Landlord PAN" hint="On tenants' rent receipts for HRA">
							<input
								v-model="form.landlord_pan"
								class="input uppercase"
								maxlength="10"
								placeholder="ABCDE1234F"
							/>
						</Field>
						<Field label="Signature on rent receipts" hint="A photo of your signature">
							<PictureInput
								:model-value="data?.receipt_signature || ''"
								buttons-only
								name="Signature"
								@update:model-value="saveSignature"
							/>
						</Field>
						<Field
							label="Landlord address"
							hint="Blank: the building's address"
							class="sm:col-span-2"
						>
							<textarea v-model="form.landlord_address" class="input" rows="2" />
						</Field>
					</div>
					<div class="mt-4 grid gap-4 sm:grid-cols-4">
						<Field label="Period (months)">
							<input
								v-model.number="form.default_agreement_months"
								type="number"
								min="0"
								class="input tabular"
							/>
						</Field>
						<Field label="Lock-in (months)">
							<input
								v-model.number="form.default_lock_in_months"
								type="number"
								min="0"
								class="input tabular"
							/>
						</Field>
						<Field label="Notice (days)">
							<input
								v-model.number="form.default_notice_days"
								type="number"
								min="0"
								class="input tabular"
							/>
						</Field>
						<Field label="Yearly increase %">
							<input
								v-model.number="form.default_rent_increase_percent"
								type="number"
								min="0"
								step="0.5"
								class="input tabular"
							/>
						</Field>
					</div>
					<Field label="House rules" hint="One rule per line" class="mt-4">
						<textarea
							v-model="houseRules"
							class="input"
							rows="5"
							placeholder="Gate closes at 11 pm&#10;No smoking inside rooms"
						/>
					</Field>
				</section>

				<!-- reminders -->
				<section class="card p-6">
					<h2 class="font-semibold">Reminders and receipts</h2>
					<div class="mt-2 divide-y divide-slate-100">
						<Toggle
							v-model="form.send_reminders"
							label="Remind tenants about unpaid rent"
							hint="With the payment link or your UPI ID"
						/>
						<div v-if="form.send_reminders" class="grid gap-4 py-3 sm:grid-cols-3">
							<Field label="Days before due date" hint="0 to skip">
								<input
									v-model.number="form.remind_days_before"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
							<Field label="Overdue: every N days" hint="0 to skip">
								<input
									v-model.number="form.overdue_reminder_interval"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
							<Field label="Overdue: at most">
								<input
									v-model.number="form.overdue_reminder_limit"
									type="number"
									min="0"
									class="input tabular"
								/>
							</Field>
						</div>
						<Toggle
							v-if="form.send_reminders"
							v-model="form.remind_on_due_date"
							label="Also remind on the due date"
						/>
						<Toggle
							v-model="form.send_receipts"
							label="Send a receipt for every payment"
						/>
						<Toggle
							v-model="form.notify_by_whatsapp"
							label="Send on WhatsApp"
							:hint="whatsappHint"
						/>
						<Toggle
							v-model="form.notify_by_email"
							label="Send by email"
							:hint="
								data.email_configured
									? 'To tenants with an email address'
									: 'Email sending isn\'t set up on this site yet'
							"
						/>
					</div>
					<details class="mt-3 rounded-xl bg-slate-50 p-4 text-sm">
						<summary class="cursor-pointer font-medium text-slate-700">
							Use your own WhatsApp Business number
						</summary>
						<p class="mt-2 text-slate-500">
							From Meta's WhatsApp Cloud API. Messages then come from your number, on
							any plan.
						</p>
						<div class="mt-3 grid gap-4 sm:grid-cols-2">
							<Field label="Phone number ID">
								<input v-model="form.whatsapp_phone_number_id" class="input" />
							</Field>
							<SecretField
								v-model="secrets.whatsapp_token"
								label="Access token"
								:saved="form.whatsapp_token_set"
							/>
						</div>
					</details>
				</section>
			</div>

			<div class="space-y-6">
				<!-- this phone: install and notifications -->
				<ThisPhone />

				<!-- message log -->
				<aside class="card h-fit">
					<div class="border-b border-slate-100 px-5 py-4">
						<h2 class="font-semibold">Recent messages</h2>
					</div>
					<EmptyState v-if="!log.length" :icon="MessageCircle" title="No messages yet" />
					<ul v-else class="divide-y divide-slate-100">
						<li v-for="m in log" :key="m.name" class="px-5 py-3 text-sm">
							<div class="flex items-center justify-between gap-2">
								<p class="truncate font-medium">{{ m.tenant_name }}</p>
								<span
									class="shrink-0 text-xs font-medium"
									:class="
										m.status === 'Sent' ? 'text-emerald-600' : 'text-rose-600'
									"
									>{{ m.status }}</span
								>
							</div>
							<p class="text-xs text-slate-500">
								{{ m.message_type }} · {{ m.channel }} ·
								{{ shortDate(m.creation.slice(0, 10)) }}
							</p>
							<p v-if="m.error" class="mt-1 text-xs text-rose-600">{{ m.error }}</p>
						</li>
					</ul>
				</aside>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Download, MessageCircle, Save } from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import Field from "@/components/Field.vue";
import PageHeader from "@/components/PageHeader.vue";
import SecretField from "@/components/SecretField.vue";
import Skeleton from "@/components/Skeleton.vue";
import PictureInput from "@/components/PictureInput.vue";
import ThisPhone from "@/components/ThisPhone.vue";
import Toggle from "@/components/Toggle.vue";
import { toast } from "@/store";
import { useResource } from "@/useResource";
import { shortDate } from "@/utils";

const { data } = useResource(() => get("get_settings"));
const messages = useResource(() => get("get_message_log"), { initial: [] });
const log = computed(() => messages.data.value || []);

const form = ref(null);
const secrets = reactive({
	razorpay_key_secret: "",
	razorpay_webhook_secret: "",
	whatsapp_token: "",
});
watch(data, (value) => value && (form.value = { ...value.settings }), { immediate: true });

// stored as HTML paragraphs, edited as lines
const houseRules = computed({
	get: () =>
		(form.value?.agreement_terms || "")
			.replace(/<\/p>\s*<p>/g, "\n")
			.replace(/<br\s*\/?>/g, "\n")
			.replace(/<[^>]+>/g, "")
			.replace(/&amp;/g, "&")
			.replace(/&lt;/g, "<")
			.replace(/&gt;/g, ">")
			.trim(),
	set: (value) => (form.value.agreement_terms = value),
});

const whatsappHint = computed(() => {
	const w = data.value?.whatsapp || {};
	if (w.source === "own") return "From your own WhatsApp Business number";
	if (w.available) return "Included in your plan";
	if (!w.in_plan)
		return "Available on Growth and Pro, or with your own WhatsApp Business number";
	return "Not set up yet";
});

async function saveSignature(picture) {
	try {
		data.value.receipt_signature = await post("save_receipt_signature", { picture });
		toast(picture ? "Signature saved" : "Signature removed");
	} catch (e) {
		toast(e.message, "error");
	}
}

const saving = ref(false);
async function save() {
	saving.value = true;
	try {
		const result = await post("save_settings", { data: { ...form.value, ...secrets } });
		data.value = result;
		Object.keys(secrets).forEach((k) => (secrets[k] = ""));
		toast("Settings saved");
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = false;
	}
}
</script>
