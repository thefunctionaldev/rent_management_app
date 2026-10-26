<template>
	<div class="min-h-screen bg-slate-50">
		<header class="bg-gradient-to-br from-brand-700 via-brand-600 to-violet-600 text-white">
			<div class="mx-auto max-w-6xl px-5 pt-8 pb-28">
				<div class="flex items-center gap-2 text-lg font-semibold">
					<img :src="logo" alt="" class="size-8 rounded-lg bg-white/90 p-1" />
					{{ info?.brand || "Rent Management" }}
				</div>
				<div class="mt-14 max-w-2xl">
					<h1 class="text-4xl font-semibold tracking-tight sm:text-5xl">
						Run your PG or hostel without the spreadsheets
					</h1>
					<p class="mt-4 text-lg text-white/80">
						Rooms and beds, monthly rent invoices, online rent collection, WhatsApp
						reminders, electricity billing and an app for your tenants.
					</p>
					<p
						class="mt-6 inline-flex items-center gap-2 rounded-full bg-white/15 px-4 py-1.5 text-sm"
					>
						<Sparkles class="size-4" /> {{ info?.trial_days || 14 }}-day free trial ·
						no card needed
					</p>
				</div>
			</div>
		</header>

		<main class="mx-auto -mt-20 grid max-w-6xl gap-8 px-5 pb-16 lg:grid-cols-[1fr_26rem]">
			<!-- plans -->
			<section class="order-2 lg:order-1">
				<div class="grid gap-4 sm:grid-cols-3 lg:mt-24">
					<div v-for="plan in info?.plans || []" :key="plan.key" class="card p-5">
						<p class="font-semibold">{{ plan.title }}</p>
						<p class="mt-1 min-h-10 text-sm text-slate-500">{{ plan.description }}</p>
						<p class="mt-3">
							<span class="tabular text-2xl font-semibold">{{
								price(plan.monthly)
							}}</span>
							<span class="text-sm text-slate-500"> / month</span>
						</p>
						<p class="text-xs text-slate-500">or {{ price(plan.yearly) }} a year</p>
						<ul class="mt-4 space-y-1.5 text-sm text-slate-600">
							<li v-for="f in plan.features" :key="f" class="flex gap-2">
								<Check class="mt-0.5 size-4 shrink-0 text-emerald-600" />{{ f }}
							</li>
						</ul>
					</div>
				</div>
			</section>

			<!-- form / progress -->
			<section class="order-1 lg:order-2">
				<div class="card p-6 shadow-xl shadow-slate-900/5">
					<template v-if="step === 'form'">
						<h2 class="text-lg font-semibold">Start your free trial</h2>
						<form class="mt-5 space-y-4" @submit.prevent="submit">
							<Field label="Your name" required>
								<input
									v-model="form.full_name"
									class="input"
									required
									autocomplete="name"
								/>
							</Field>
							<Field label="PG / hostel name" required>
								<input
									v-model="form.business_name"
									class="input"
									required
									placeholder="Sunrise PG"
								/>
							</Field>
							<div class="grid grid-cols-2 gap-3">
								<Field label="Email" required>
									<input
										v-model="form.email"
										type="email"
										class="input"
										required
										autocomplete="email"
									/>
								</Field>
								<Field label="Mobile">
									<input
										v-model="form.phone"
										type="tel"
										class="input"
										autocomplete="tel"
									/>
								</Field>
							</div>
							<Field label="Your web address" required :hint="addressHint">
								<div
									class="flex items-center rounded-lg border border-slate-200 bg-white focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-100"
								>
									<input
										v-model="form.subdomain"
										class="min-w-0 flex-1 rounded-l-lg border-0 bg-transparent px-3 py-2 text-sm focus:ring-0 focus:outline-none"
										required
										placeholder="sunrise-pg"
										@input="checkLater"
									/>
									<span class="shrink-0 pr-3 text-sm text-slate-500"
										>.{{ info?.domain }}</span
									>
								</div>
							</Field>
							<div class="grid grid-cols-2 gap-3">
								<Field label="City"
									><input v-model="form.city" class="input"
								/></Field>
								<Field label="Beds (about)">
									<input
										v-model.number="form.beds"
										type="number"
										min="1"
										class="input tabular"
									/>
								</Field>
							</div>
							<!-- honeypot: hidden from people, filled in by bots -->
							<input
								v-model="form.website"
								class="hidden"
								tabindex="-1"
								autocomplete="off"
								aria-hidden="true"
							/>
							<Button
								type="submit"
								variant="primary"
								size="lg"
								class="w-full"
								:loading="busy"
								>Create my account</Button
							>
							<p class="text-center text-xs text-slate-500">
								We'll email you a link to confirm your address.
							</p>
						</form>
					</template>

					<div v-else-if="step === 'sent'" class="py-6 text-center">
						<span
							class="mx-auto grid size-12 place-items-center rounded-full bg-brand-50 text-brand-600"
							><Mail class="size-6"
						/></span>
						<h2 class="mt-4 text-lg font-semibold">Check your email</h2>
						<p class="mt-2 text-sm text-slate-600">
							We sent a link to <b>{{ form.email }}</b
							>. Click it to create your account.
						</p>
					</div>

					<div v-else-if="step === 'progress'" class="py-6 text-center">
						<div
							class="mx-auto size-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"
						/>
						<h2 class="mt-5 text-lg font-semibold">
							Setting up {{ status?.business_name }}
						</h2>
						<p class="mt-2 text-sm text-slate-600">
							Creating {{ status?.site }}. This takes a minute or two; keep this page
							open.
						</p>
					</div>

					<div v-else-if="step === 'ready'" class="py-4 text-center">
						<span
							class="mx-auto grid size-12 place-items-center rounded-full bg-emerald-50 text-emerald-600"
							><CircleCheck class="size-7"
						/></span>
						<h2 class="mt-4 text-lg font-semibold">You're all set</h2>
						<p class="mt-2 text-sm text-slate-600">
							Your account is at
							<a :href="status.url" class="font-medium text-brand-600">{{
								status.site
							}}</a
							>.
						</p>
						<Button
							v-if="status.set_password_link"
							variant="primary"
							size="lg"
							class="mt-5 w-full"
							:href="status.set_password_link"
							>Set your password</Button
						>
						<Button v-else class="mt-5 w-full" :href="status.url">Log in</Button>
					</div>

					<div v-else class="py-6 text-center">
						<h2 class="text-lg font-semibold">Something went wrong</h2>
						<p class="mt-2 text-sm text-slate-600">
							We couldn't finish setting up your account. We've been told and will
							email you shortly.
						</p>
					</div>
				</div>
			</section>
		</main>
		<Toasts />
	</div>
</template>

<script setup>
import { Check, CircleCheck, Mail, Sparkles } from "lucide-vue-next";
import { onMounted, reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Toasts from "@/components/Toasts.vue";
import { toast } from "@/store";

const M = "rent_management.signup.";
const logo = "/assets/rent_management/frontend/favicon.svg";
const info = ref(null);
const step = ref("form");
const busy = ref(false);
const status = ref(null);
const addressHint = ref("Letters, numbers and hyphens");
const form = reactive({
	full_name: "",
	business_name: "",
	email: "",
	phone: "",
	subdomain: "",
	city: "",
	beds: "",
	website: "",
});

const price = (amount) =>
	new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: info.value?.currency || "INR",
		maximumFractionDigits: 0,
	}).format(amount || 0);

let timer;
function checkLater() {
	form.subdomain = form.subdomain.toLowerCase().replace(/[^a-z0-9-]/g, "");
	clearTimeout(timer);
	timer = setTimeout(async () => {
		if (form.subdomain.length < 3) return;
		const result = await get(M + "is_available", { subdomain: form.subdomain }).catch(
			() => null
		);
		if (result)
			addressHint.value = result.available ? `${result.site} is available` : result.message;
	}, 400);
}

async function submit() {
	busy.value = true;
	try {
		const result = await post(M + "signup", { ...form });
		if (result.token) {
			// verification skipped (test servers): go straight to the progress screen
			follow(result.token);
		} else {
			step.value = "sent";
		}
	} catch (e) {
		toast(e.message, "error");
	} finally {
		busy.value = false;
	}
}

async function follow(token) {
	step.value = "progress";
	for (;;) {
		try {
			status.value = await get(M + "get_status", { token });
		} catch (e) {
			toast(e.message, "error");
			step.value = "failed";
			return;
		}
		if (status.value.status === "Active") return (step.value = "ready");
		if (status.value.status === "Failed") return (step.value = "failed");
		await new Promise((r) => setTimeout(r, 3000));
	}
}

onMounted(async () => {
	info.value = await get(M + "get_plans").catch(() => null);
	const token = new URLSearchParams(window.location.search).get("token");
	if (token) {
		step.value = "progress";
		try {
			await post(M + "verify", { token });
			follow(token);
		} catch (e) {
			toast(e.message, "error");
			step.value = "failed";
		}
	}
});
</script>
