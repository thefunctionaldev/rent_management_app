<template>
	<div>
		<RouterLink
			to="/tenants"
			class="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"
		>
			<ChevronLeft class="size-4" /> Tenants
		</RouterLink>

		<div v-if="!data" class="space-y-4">
			<Skeleton class="h-36 rounded-2xl" />
			<Skeleton class="h-64 rounded-2xl" />
		</div>

		<template v-else>
			<!-- profile header -->
			<div class="card overflow-hidden">
				<div class="h-20 bg-gradient-to-r from-brand-500 via-violet-500 to-fuchsia-500" />
				<div
					class="flex flex-col gap-4 px-6 pb-6 sm:flex-row sm:items-start sm:justify-between"
				>
					<div class="flex items-start gap-4">
						<Avatar
							:name="tenant.full_name"
							:image="tenant.display_picture"
							size="lg"
							class="-mt-7 ring-4 ring-white"
						/>
						<div class="pt-3">
							<div class="flex items-center gap-2">
								<h1 class="text-xl font-semibold tracking-tight">
									{{ tenant.full_name }}
								</h1>
								<StatusBadge :status="tenant.status" />
							</div>
							<div
								class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500"
							>
								<a
									v-if="tenant.mobile_no"
									:href="`tel:${tenant.mobile_no}`"
									class="inline-flex items-center gap-1.5 hover:text-slate-900"
									><Phone class="size-3.5" />{{ tenant.mobile_no }}</a
								>
								<a
									v-if="tenant.email_id"
									:href="`mailto:${tenant.email_id}`"
									class="inline-flex items-center gap-1.5 hover:text-slate-900"
									><Mail class="size-3.5" />{{ tenant.email_id }}</a
								>
								<span
									v-if="tenant.occupation"
									class="inline-flex items-center gap-1.5"
									><Briefcase class="size-3.5" />{{ tenant.occupation }}</span
								>
							</div>
						</div>
					</div>
					<div class="flex gap-2 sm:pt-3">
						<Button :icon="Pencil" @click="openDialog('tenant', { tenant })"
							>Edit</Button
						>
						<Button
							v-if="!current"
							variant="primary"
							:icon="KeyRound"
							@click="openDialog('allotRoom', { tenantName: tenant.name })"
							>Allot room</Button
						>
					</div>
				</div>
			</div>

			<div class="mt-6 grid gap-6 lg:grid-cols-3">
				<!-- left: stay + totals -->
				<div class="space-y-6">
					<div class="card p-5">
						<h2 class="font-semibold">Current stay</h2>
						<template v-if="current">
							<div class="mt-4 flex items-center gap-3">
								<span
									class="grid size-11 place-items-center rounded-xl bg-brand-50 text-brand-600"
									><DoorOpen class="size-5"
								/></span>
								<div>
									<p class="font-semibold">
										Room {{ current.room
										}}<span
											v-if="current.bed_no"
											class="font-normal text-slate-500"
										>
											· Bed {{ current.bed_no }}</span
										>
									</p>
									<p class="text-sm text-slate-500">
										{{ current.property ? `${current.property} · ` : ""
										}}{{ current.room_type || "Room" }} · since
										{{ date(current.allotment_date) }}
									</p>
								</div>
							</div>
							<dl class="mt-4 space-y-2 text-sm">
								<div class="flex justify-between">
									<dt class="text-slate-500">Monthly rent</dt>
									<dd class="tabular font-medium">
										{{ money(current.rent_amount) }}
									</dd>
								</div>
								<div class="flex justify-between">
									<dt class="text-slate-500">Deposit</dt>
									<dd class="tabular font-medium">
										{{ money(current.security_deposit) }}
										<span
											v-if="current.security_deposit"
											:class="
												current.deposit_collected
													? 'text-emerald-600'
													: 'text-amber-600'
											"
											class="ml-1 text-xs"
										>
											{{
												current.deposit_collected ? "collected" : "pending"
											}}
										</span>
									</dd>
								</div>
								<div
									v-if="current.agreement_end_date"
									class="flex justify-between"
								>
									<dt class="text-slate-500">Agreement until</dt>
									<dd>{{ date(current.agreement_end_date) }}</dd>
								</div>
								<div v-if="current.lock_in_months" class="flex justify-between">
									<dt class="text-slate-500">Lock-in</dt>
									<dd>{{ current.lock_in_months }} months</dd>
								</div>
								<div class="flex justify-between">
									<dt class="text-slate-500">Notice period</dt>
									<dd>{{ current.notice_period_days || 0 }} days</dd>
								</div>
								<div
									v-if="current.next_rent_increase_date"
									class="flex justify-between"
								>
									<dt class="text-slate-500">Next increase</dt>
									<dd>
										{{ current.rent_increase_percent }}% on
										{{ date(current.next_rent_increase_date) }}
									</dd>
								</div>
							</dl>
							<div
								v-if="current.expected_vacate_date"
								class="mt-4 flex items-start justify-between gap-3 rounded-xl bg-amber-50 px-3 py-2.5 text-sm text-amber-800"
							>
								<p>
									Gave notice on {{ date(current.notice_given_on) }}; moving out
									<b>{{ date(current.expected_vacate_date) }}</b>
								</p>
								<button
									class="shrink-0 text-xs font-medium underline"
									@click="withdrawNotice"
								>
									Withdraw
								</button>
							</div>
							<div class="mt-5 grid grid-cols-2 gap-2">
								<Button
									size="sm"
									:icon="FilePlus"
									@click="openDialog('invoice', { allotment: current.name })"
									>Invoice</Button
								>
								<Button
									size="sm"
									:icon="LogOut"
									@click="
										openDialog('vacate', {
											allotment: current.name,
											room: current.room,
											tenantName: tenant.full_name,
										})
									"
									>Vacate</Button
								>
								<Button
									size="sm"
									:icon="BellRing"
									:disabled="!!current.expected_vacate_date"
									@click="
										openDialog('notice', {
											allotment: current,
											tenantName: tenant.full_name,
										})
									"
									>Give notice</Button
								>
								<Button
									size="sm"
									:icon="IndianRupee"
									@click="
										openDialog('changeRent', {
											allotment: current,
											tenantName: tenant.full_name,
										})
									"
									>Change rent</Button
								>
								<Button
									size="sm"
									class="col-span-2"
									:icon="FileText"
									:href="agreementUrl(current)"
									target="_blank"
									>Rental agreement (PDF)</Button
								>
								<Button
									v-if="current.security_deposit && !current.deposit_collected"
									size="sm"
									class="col-span-2"
									:icon="ShieldCheck"
									@click="
										openDialog('collectDeposit', {
											allotment: {
												...current,
												tenant_name: tenant.full_name,
											},
										})
									"
									>Mark deposit collected</Button
								>
							</div>
						</template>
						<p v-else class="mt-3 text-sm text-slate-500">
							Not staying in any room right now.
						</p>
					</div>

					<div class="card divide-y divide-slate-100">
						<div
							v-for="s in stats"
							:key="s.label"
							class="flex items-center justify-between px-5 py-4"
						>
							<p class="text-sm text-slate-500">{{ s.label }}</p>
							<p class="tabular font-semibold" :class="s.class">
								{{ money(s.value) }}
							</p>
						</div>
					</div>

					<div v-if="current" class="card p-5">
						<div class="flex items-start justify-between gap-3">
							<div>
								<h2 class="font-semibold">Check-in</h2>
								<p class="text-sm text-slate-500">{{ checkinText }}</p>
							</div>
							<StatusBadge v-if="checkin" :status="checkinStatus" />
						</div>
						<div class="mt-3 flex flex-wrap gap-2">
							<Button
								v-if="checkin?.status !== 'Signed'"
								size="sm"
								:icon="Send"
								:loading="sendingCheckin"
								@click="sendCheckin"
								>{{
									checkin?.url ? "Send link again" : "Send check-in link"
								}}</Button
							>
							<Button
								size="sm"
								:icon="ShieldCheck"
								:href="`/api/method/rent_management.api.download_verification_form?allotment=${encodeURIComponent(
									current.name
								)}`"
								>Police verification form</Button
							>
						</div>
					</div>

					<div class="card p-5">
						<div class="flex items-center justify-between gap-3">
							<div>
								<h2 class="font-semibold">Tenant app</h2>
								<p class="text-sm text-slate-500">
									{{
										tenant.user
											? `Invited as ${tenant.user}`
											: "Bills, online payment and requests on their phone"
									}}
								</p>
							</div>
							<Button
								size="sm"
								:icon="Smartphone"
								:loading="inviting"
								@click="invite"
								>{{ tenant.user ? "Resend" : "Invite" }}</Button
							>
						</div>
						<div v-if="inviteLink" class="mt-3 rounded-lg bg-slate-50 p-3 text-xs">
							<p class="text-slate-600">
								{{
									inviteEmailed
										? "Emailed. You can also send this link on WhatsApp:"
										: "Email isn't set up, so send the tenant this link to set their password:"
								}}
							</p>
							<p class="mt-1 font-mono break-all text-slate-800">{{ inviteLink }}</p>
						</div>
					</div>

					<div class="card p-5">
						<h2 class="font-semibold">Details</h2>
						<dl class="mt-3 space-y-2.5 text-sm">
							<div
								v-for="row in details"
								:key="row.label"
								class="flex justify-between gap-4"
							>
								<dt class="text-slate-500">{{ row.label }}</dt>
								<dd class="text-right text-slate-900">
									<a
										v-if="row.link"
										:href="row.link"
										target="_blank"
										class="font-medium text-brand-600 hover:underline"
										>{{ row.value }}</a
									>
									<template v-else>{{ row.value || "—" }}</template>
									<button
										v-if="row.reveal"
										class="ml-1 text-xs font-medium text-brand-600 hover:underline"
										@click="row.reveal"
									>
										{{ aadhaar ? "Hide" : "Show" }}
									</button>
								</dd>
							</div>
						</dl>
					</div>
				</div>

				<!-- right: activity -->
				<div class="card lg:col-span-2">
					<div class="px-5 pt-4">
						<Tabs v-model="tab" :tabs="tabs" />
					</div>
					<div v-if="tab === 'invoices'">
						<EmptyState
							v-if="!data.invoices.length"
							:icon="FileText"
							title="No invoices yet"
						/>
						<ul v-else class="divide-y divide-slate-100">
							<li
								v-for="inv in data.invoices"
								:key="inv.name"
								class="flex items-center gap-4 px-5 py-3.5"
							>
								<div class="min-w-0 flex-1">
									<p class="text-sm font-medium">
										{{ inv.billing_month }} {{ inv.billing_year }}
									</p>
									<p class="text-xs text-slate-500">
										{{ inv.name }} · Room {{ inv.room }} · due
										{{ date(inv.due_date) }}
									</p>
								</div>
								<div class="text-right">
									<p class="tabular text-sm font-semibold">
										{{ money(inv.final_amount) }}
									</p>
									<p
										v-if="inv.docstatus === 1 && inv.outstanding_amount"
										class="tabular text-xs text-amber-700"
									>
										{{ money(inv.outstanding_amount) }} due
									</p>
								</div>
								<StatusBadge :status="inv.status" class="w-24 justify-center" />
								<Button
									v-if="inv.docstatus === 1 && inv.outstanding_amount > 0"
									size="sm"
									@click="openDialog('recordPayment', { invoice: inv })"
									>Collect</Button
								>
							</li>
						</ul>
					</div>
					<div v-else-if="tab === 'payments'">
						<EmptyState
							v-if="!data.payments.length"
							:icon="Wallet"
							title="No payments yet"
						/>
						<ul v-else class="divide-y divide-slate-100">
							<li
								v-for="p in data.payments"
								:key="p.name"
								class="flex items-center gap-4 px-5 py-3.5"
							>
								<span
									class="grid size-8 place-items-center rounded-full bg-emerald-50 text-emerald-600"
									><ArrowDownLeft class="size-4"
								/></span>
								<div class="min-w-0 flex-1">
									<p class="text-sm font-medium">
										{{ p.mode_of_payment
										}}<span v-if="p.reference_no" class="text-slate-400">
											· {{ p.reference_no }}</span
										>
									</p>
									<p class="text-xs text-slate-500">
										{{ date(p.payment_date) }} · {{ p.rent_invoice }}
									</p>
								</div>
								<p class="tabular text-sm font-semibold text-emerald-600">
									+{{ money(p.amount) }}
								</p>
							</li>
						</ul>
					</div>
					<div v-else>
						<EmptyState
							v-if="!data.allotments.length"
							:icon="DoorOpen"
							title="No stays yet"
						/>
						<ol v-else class="space-y-0 px-5 py-4">
							<li
								v-for="a in data.allotments"
								:key="a.name"
								class="relative border-l-2 border-slate-100 pb-6 pl-6 last:pb-0"
							>
								<span
									class="absolute top-1 -left-[7px] size-3 rounded-full ring-4 ring-white"
									:class="
										a.status === 'Active' ? 'bg-emerald-500' : 'bg-slate-300'
									"
								/>
								<div class="flex items-center gap-2">
									<p class="text-sm font-medium">Room {{ a.room }}</p>
									<StatusBadge :status="a.status" />
								</div>
								<p class="mt-0.5 text-xs text-slate-500">
									{{ date(a.allotment_date) }} →
									{{ a.vacate_date ? date(a.vacate_date) : "present" }} ·
									{{ money(a.rent_amount) }}/mo
								</p>
								<p
									v-for="r in a.rent_revisions"
									:key="r.effective_from"
									class="mt-1 text-xs text-slate-500"
								>
									Rent {{ money(r.old_rent) }} → {{ money(r.new_rent) }} from
									{{ date(r.effective_from)
									}}<template v-if="r.reason"> · {{ r.reason }}</template>
								</p>
								<p
									v-if="a.deposit_settlement"
									class="mt-1 text-xs text-emerald-600"
								>
									Deposit settled ({{ a.deposit_settlement }})
								</p>
							</li>
						</ol>
					</div>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import {
	Smartphone,
	ArrowDownLeft,
	BellRing,
	IndianRupee,
	Briefcase,
	ChevronLeft,
	DoorOpen,
	FilePlus,
	FileText,
	KeyRound,
	LogOut,
	Mail,
	Pencil,
	Phone,
	Send,
	ShieldCheck,
	Wallet,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import { get, post } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import Tabs from "@/components/Tabs.vue";
import { openDialog } from "@/dialogs";
import { bumpData, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

const props = defineProps({ name: { type: String, required: true } });
const { data } = useResource(() => get("get_tenant", { name: props.name }));

const tenant = computed(() => data.value.tenant);

const inviting = ref(false);
const inviteLink = ref("");
const inviteEmailed = ref(false);
async function invite() {
	if (!tenant.value.email_id) {
		toast("Add the tenant's email address first (Edit)", "error");
		return;
	}
	inviting.value = true;
	try {
		const result = await post("invite_tenant", { name: props.name });
		inviteLink.value = result.link;
		inviteEmailed.value = result.emailed;
		toast(result.emailed ? "Invite sent" : "Login created");
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		inviting.value = false;
	}
}

const agreementUrl = (a) =>
	`/api/method/rent_management.api.download_agreement?allotment=${encodeURIComponent(a.name)}`;
async function withdrawNotice() {
	try {
		await post("withdraw_notice", { allotment: current.value.name });
		toast("Notice withdrawn");
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	}
}

// the full number is fetched on demand (the view is logged) and hidden again after a minute
const aadhaar = ref("");
let hideTimer;
async function toggleAadhaar() {
	clearTimeout(hideTimer);
	if (aadhaar.value) {
		aadhaar.value = "";
		return;
	}
	try {
		aadhaar.value = await post("reveal_aadhaar", { name: props.name });
		hideTimer = setTimeout(() => (aadhaar.value = ""), 60000);
	} catch (e) {
		toast(e.message, "error");
	}
}
const current = computed(() => data.value.allotments.find((a) => a.status === "Active"));
const tab = ref("invoices");
const tabs = computed(() => [
	{ value: "invoices", label: "Invoices", count: data.value?.invoices.length },
	{ value: "payments", label: "Payments", count: data.value?.payments.length },
	{ value: "stays", label: "Stays", count: data.value?.allotments.length },
]);
const stats = computed(() => [
	{ label: "Total invoiced", value: data.value.totals.invoiced, class: "" },
	{ label: "Total paid", value: data.value.totals.paid, class: "text-emerald-600" },
	{
		label: "Outstanding",
		value: data.value.totals.outstanding,
		class: data.value.totals.outstanding ? "text-amber-700" : "",
	},
]);
const checkin = computed(() => data.value.checkin);
const checkinStatus = computed(() =>
	checkin.value?.expired
		? "Expired"
		: { Sent: "Link sent", "Details Submitted": "Details in" }[checkin.value?.status] ||
		  checkin.value?.status
);
const checkinText = computed(() => {
	const c = checkin.value;
	if (!c)
		return "Let them fill in their details, upload their ID and sign the agreement on their phone.";
	if (c.status === "Signed")
		return `Agreement signed by ${c.signed_name} on ${date(c.signed_on.slice(0, 10))}${
			c.otp_channel && c.otp_channel !== "None"
				? `, with a code sent by ${c.otp_channel}`
				: ""
		}.`;
	if (c.expired) return "The link expired before they finished. Send a new one.";
	if (c.status === "Details Submitted")
		return "Their details and ID are in. Waiting for them to sign.";
	return `Link sent on ${date(c.sent_on.slice(0, 10))}. Waiting for them.`;
});

const sendingCheckin = ref(false);
async function sendCheckin() {
	sendingCheckin.value = true;
	try {
		const result = await post("send_checkin", { allotment: current.value.name });
		const digits = (result.mobile_no || "").replace(/[^\d]/g, "");
		const text = `Hello ${tenant.value.first_name}, welcome! Please fill in your details, upload your ID and sign your rental agreement here: ${result.url}`;
		window.open(
			`https://wa.me/${
				digits.length === 10 ? `91${digits}` : digits
			}?text=${encodeURIComponent(text)}`,
			"_blank"
		);
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		sendingCheckin.value = false;
	}
}

const details = computed(() => [
	{ label: "Gender", value: tenant.value.gender },
	{
		label: "Date of birth",
		value: tenant.value.date_of_birth ? date(tenant.value.date_of_birth) : "",
	},
	{ label: "Father / guardian", value: tenant.value.guardian_name },
	{
		label: "Aadhaar",
		value:
			aadhaar.value ||
			(tenant.value.aadhar_last4 && `•••• •••• ${tenant.value.aadhar_last4}`),
		reveal: tenant.value.aadhar_last4 ? toggleAadhaar : null,
	},
	{ label: "Workplace", value: tenant.value.workspace },
	{ label: "Monthly income", value: tenant.value.salary ? money(tenant.value.salary) : "" },
	{ label: "Address", value: tenant.value.permanent_address },
	{
		label: "Emergency contact",
		value: [
			tenant.value.emergency_contact_name,
			tenant.value.emergency_contact_relation &&
				`(${tenant.value.emergency_contact_relation})`,
			tenant.value.emergency_contact_phone,
		]
			.filter(Boolean)
			.join(" "),
	},
	{
		label: "Aadhaar card",
		value: tenant.value.aadhar_card ? "Uploaded" : "",
		link: tenant.value.aadhar_card,
	},
]);
</script>
