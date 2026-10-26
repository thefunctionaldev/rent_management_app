<template>
	<div>
		<PageHeader title="Settings" subtitle="Invoicing, online rent collection and reminders">
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
								:class="m.status === 'Sent' ? 'text-emerald-600' : 'text-rose-600'"
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
</template>

<script setup>
import { MessageCircle, Save } from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import Field from "@/components/Field.vue";
import PageHeader from "@/components/PageHeader.vue";
import SecretField from "@/components/SecretField.vue";
import Skeleton from "@/components/Skeleton.vue";
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

const whatsappHint = computed(() => {
	const w = data.value?.whatsapp || {};
	if (w.source === "own") return "From your own WhatsApp Business number";
	if (w.available) return "Included in your plan";
	if (!w.in_plan)
		return "Available on Growth and Pro, or with your own WhatsApp Business number";
	return "Not set up yet";
});

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
