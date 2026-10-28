<template>
	<div class="min-h-screen bg-slate-50 text-slate-900">
		<p
			v-if="listing?.referred_by"
			class="bg-emerald-600 px-5 py-2.5 text-center text-sm font-medium text-white"
		>
			{{ listing.referred_by.name }} sent you here<template
				v-if="listing.referred_by.discount"
			>
				· you get {{ money(listing.referred_by.discount) }} off your first month when you
				move in</template
			>
		</p>
		<div v-if="loading" class="grid min-h-screen place-items-center">
			<div
				class="size-8 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600"
			/>
		</div>

		<div v-else-if="error" class="grid min-h-screen place-items-center px-6 text-center">
			<div>
				<p class="text-lg font-semibold">This page isn't available</p>
				<p class="mt-1 text-sm text-slate-500">{{ error }}</p>
				<a href="/stay" class="mt-4 inline-block text-sm font-medium text-brand-600"
					>See all buildings</a
				>
			</div>
		</div>

		<!-- all buildings -->
		<template v-else-if="!slug">
			<header
				class="bg-gradient-to-br from-brand-700 via-brand-600 to-violet-600 text-white"
			>
				<div class="mx-auto max-w-6xl px-5 pt-10 pb-24">
					<p class="text-sm font-medium text-white/70">{{ listing.brand }}</p>
					<h1 class="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
						Rooms and beds in {{ cities }}
					</h1>
					<p class="mt-2 text-white/80">
						{{ totalFree }} bed{{ totalFree === 1 ? "" : "s" }} free right now. Visit,
						or hold yours online.
					</p>
				</div>
			</header>
			<main
				class="mx-auto -mt-16 grid max-w-6xl gap-5 px-5 pb-16 sm:grid-cols-2 lg:grid-cols-3"
			>
				<a
					v-for="b in listing.buildings"
					:key="b.slug"
					:href="`/stay/${b.slug}`"
					class="card group overflow-hidden transition hover:-translate-y-0.5 hover:shadow-lg"
				>
					<div class="relative h-44 bg-slate-200">
						<img
							v-if="b.image"
							:src="b.image"
							:alt="b.name"
							class="size-full object-cover"
						/>
						<span
							class="absolute top-3 left-3 rounded-full bg-white/95 px-2.5 py-1 text-xs font-medium"
							:class="b.free_beds ? 'text-emerald-700' : 'text-slate-500'"
							>{{
								b.free_beds
									? `${b.free_beds} bed${b.free_beds === 1 ? "" : "s"} free`
									: "Full"
							}}</span
						>
					</div>
					<div class="p-5">
						<p class="font-semibold group-hover:text-brand-700">{{ b.name }}</p>
						<p class="mt-0.5 text-sm text-slate-500">
							{{ [b.address, b.city].filter(Boolean).join(", ") }}
						</p>
						<div class="mt-3 flex flex-wrap gap-1.5">
							<span
								v-for="tag in tags(b)"
								:key="tag"
								class="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600"
								>{{ tag }}</span
							>
						</div>
						<p v-if="b.rent_from" class="mt-4 text-sm text-slate-500">
							from
							<span class="tabular text-lg font-semibold text-slate-900">{{
								money(b.rent_from)
							}}</span>
							/ month
						</p>
					</div>
				</a>
			</main>
		</template>

		<!-- one building -->
		<template v-else-if="building">
			<header class="relative h-72 overflow-hidden bg-brand-700 text-white sm:h-96">
				<img
					v-if="building.image"
					:src="building.image"
					:alt="building.name"
					class="absolute inset-0 size-full object-cover"
				/>
				<div
					class="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/30 to-transparent"
				/>
				<div
					class="relative mx-auto flex h-full max-w-6xl flex-col justify-between px-5 py-6"
				>
					<a
						v-if="listing.buildings_count !== 1"
						href="/stay"
						class="inline-flex w-fit items-center gap-1 rounded-full bg-black/30 px-3 py-1 text-sm backdrop-blur"
					>
						<ChevronLeft class="size-4" /> All buildings
					</a>
					<span v-else />
					<div>
						<div class="flex flex-wrap gap-1.5">
							<span
								v-for="tag in tags(building)"
								:key="tag"
								class="rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-medium backdrop-blur"
								>{{ tag }}</span
							>
						</div>
						<h1 class="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
							{{ building.name }}
						</h1>
						<p class="mt-1 flex items-center gap-1.5 text-white/85">
							<MapPin class="size-4" />
							{{ [building.address, building.city].filter(Boolean).join(", ") }}
							<a
								v-if="building.map_link"
								:href="building.map_link"
								target="_blank"
								rel="noopener"
								class="ml-1 underline"
								>Map</a
							>
						</p>
					</div>
				</div>
			</header>

			<main class="mx-auto grid max-w-6xl gap-8 px-5 py-8 lg:grid-cols-[1fr_24rem]">
				<div class="space-y-8">
					<!-- booking status after enquiring / paying -->
					<section v-if="booking" ref="bookingCard" class="card p-6">
						<template v-if="booking.token_status === 'Paid'">
							<div class="flex items-start gap-3">
								<span
									class="grid size-11 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-600"
									><CircleCheck class="size-6"
								/></span>
								<div>
									<p class="text-lg font-semibold">
										Your bed is held, {{ booking.name }}!
									</p>
									<p class="mt-1 text-sm text-slate-600">
										We received your token of
										{{ money(booking.token_amount) }} for a
										{{ booking.room_type }} bed. It counts towards your first
										month's rent. We'll call you to fix the move-in.
									</p>
								</div>
							</div>
						</template>
						<template v-else-if="booking.token_status === 'Reported'">
							<p class="text-lg font-semibold">Thank you, {{ booking.name }}</p>
							<p class="mt-1 text-sm text-slate-600">
								We'll check your UPI payment of
								{{ money(booking.token_amount) }} and confirm your bed shortly.
							</p>
						</template>
						<template v-else-if="booking.token_status === 'Pending'">
							<p class="text-lg font-semibold">Hold your bed, {{ booking.name }}</p>
							<p class="mt-1 text-sm text-slate-600">
								Pay a token of
								<b class="text-slate-900">{{ money(booking.token_amount) }}</b> to
								hold a {{ booking.room_type }} bed. It counts towards your first
								month's rent.
							</p>
							<div class="mt-4 flex flex-wrap gap-3">
								<Button
									v-if="booking.online"
									variant="primary"
									size="lg"
									:icon="CreditCard"
									:loading="paying"
									@click="payOnline"
									>Pay {{ money(booking.token_amount) }} online</Button
								>
								<Button
									v-if="booking.upi_link"
									size="lg"
									:icon="Smartphone"
									:href="booking.upi_link"
									class="sm:hidden"
									>Pay with a UPI app</Button
								>
							</div>
							<div
								v-if="booking.upi_qr"
								class="mt-5 flex flex-col gap-4 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center"
							>
								<img
									:src="booking.upi_qr"
									alt="UPI QR code"
									class="size-36 rounded-lg bg-white"
								/>
								<div class="flex-1 space-y-2">
									<p class="text-sm font-medium">Or scan to pay by UPI</p>
									<p class="text-xs text-slate-500">
										After paying, enter the UPI reference so we can find it.
									</p>
									<div class="flex gap-2">
										<input
											v-model="reference"
											class="input"
											placeholder="UPI reference (12 digits)"
										/>
										<Button :loading="reporting" @click="reportPaid"
											>I've paid</Button
										>
									</div>
								</div>
							</div>
						</template>
						<template v-else>
							<p class="text-lg font-semibold">Thank you, {{ booking.name }}!</p>
							<p class="mt-1 text-sm text-slate-600">
								<template v-if="booking.visit_on">
									We'll see you on {{ when(booking.visit_on) }}. We'll call to
									confirm.
								</template>
								<template v-else>We'll call you shortly.</template>
							</p>
						</template>
					</section>

					<section v-if="building.description">
						<h2 class="text-lg font-semibold">About</h2>
						<p class="mt-2 whitespace-pre-line text-slate-600">
							{{ building.description }}
						</p>
					</section>

					<section v-if="building.amenities.length">
						<h2 class="text-lg font-semibold">Amenities</h2>
						<ul class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
							<li
								v-for="a in building.amenities"
								:key="a"
								class="flex items-center gap-2 text-sm text-slate-700"
							>
								<Check class="size-4 shrink-0 text-emerald-600" />{{ a }}
							</li>
						</ul>
					</section>

					<section>
						<h2 class="text-lg font-semibold">Rooms</h2>
						<div class="mt-3 grid gap-4 sm:grid-cols-2">
							<div
								v-for="rt in building.room_types"
								:key="rt.type"
								class="card flex flex-col p-5"
							>
								<div class="flex items-start justify-between gap-2">
									<p class="font-semibold">{{ rt.type }}</p>
									<span
										class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
										:class="
											rt.free
												? 'bg-emerald-50 text-emerald-700'
												: 'bg-slate-100 text-slate-500'
										"
										>{{
											rt.free
												? `${rt.free} bed${rt.free === 1 ? "" : "s"} free`
												: "Full"
										}}</span
									>
								</div>
								<p v-if="rt.description" class="mt-1 text-sm text-slate-500">
									{{ rt.description }}
								</p>
								<p class="mt-3">
									<span class="tabular text-2xl font-semibold">{{
										money(rt.rent)
									}}</span>
									<span class="text-sm text-slate-500"> / month</span>
								</p>
								<p class="text-xs text-slate-500">
									<template v-if="rt.deposit"
										>Deposit {{ money(rt.deposit) }} ·
									</template>
									{{ rt.furnished ? "Furnished" : "Unfurnished" }}
									<template v-if="rt.attached_bathroom">
										· Attached bathroom</template
									>
								</p>
								<div class="mt-4 flex gap-2">
									<Button
										v-if="rt.free && listing.token"
										variant="primary"
										size="sm"
										class="flex-1"
										@click="choose(rt, true)"
										>Book a bed</Button
									>
									<Button size="sm" class="flex-1" @click="choose(rt, false)">{{
										rt.free ? "Enquire" : "Join waitlist"
									}}</Button>
								</div>
							</div>
						</div>
					</section>
				</div>

				<!-- enquiry form -->
				<aside class="lg:sticky lg:top-6 lg:self-start">
					<form ref="formCard" class="card space-y-4 p-5" @submit.prevent="submit">
						<div>
							<p class="font-semibold">
								{{ form.book ? "Book a bed" : "Enquire or book a visit" }}
							</p>
							<p class="text-sm text-slate-500">We'll call you back.</p>
						</div>
						<Field label="Your name" required>
							<input
								v-model="form.name"
								class="input"
								required
								autocomplete="name"
							/>
						</Field>
						<Field label="Mobile number" required>
							<input
								v-model="form.mobile_no"
								class="input"
								type="tel"
								required
								autocomplete="tel"
								placeholder="98765 43210"
							/>
						</Field>
						<Field label="Email">
							<input
								v-model="form.email_id"
								class="input"
								type="email"
								autocomplete="email"
							/>
						</Field>
						<div class="grid grid-cols-2 gap-3">
							<Field label="Room">
								<select v-model="form.room_type" class="input">
									<option value="">Any</option>
									<option
										v-for="rt in building.room_types"
										:key="rt.type"
										:value="rt.type"
									>
										{{ rt.type }}
									</option>
								</select>
							</Field>
							<Field label="Moving in">
								<input
									v-model="form.move_in_date"
									class="input"
									type="date"
									:min="listing.today"
								/>
							</Field>
						</div>
						<label class="flex items-center gap-2 text-sm">
							<input
								v-model="wantsVisit"
								type="checkbox"
								class="size-4 accent-brand-600"
							/>
							I'd like to visit first
						</label>
						<div v-if="wantsVisit" class="grid grid-cols-2 gap-3">
							<Field label="Day">
								<input
									v-model="visitDay"
									class="input"
									type="date"
									:min="listing.today"
									required
								/>
							</Field>
							<Field label="Time">
								<select v-model="visitTime" class="input">
									<option v-for="t in visitTimes" :key="t" :value="t">
										{{ t }}
									</option>
								</select>
							</Field>
						</div>
						<Field label="Message">
							<textarea
								v-model="form.message"
								class="input"
								rows="2"
								placeholder="Anything we should know?"
							/>
						</Field>
						<label
							v-if="canBook"
							class="flex items-start gap-3 rounded-xl border border-brand-200 bg-brand-50/60 p-3 text-sm"
						>
							<input
								v-model="form.book"
								type="checkbox"
								class="mt-0.5 size-4 accent-brand-600"
							/>
							<span>
								<span class="font-medium">Hold a bed now</span>
								<span class="block text-slate-600"
									>Pay a {{ money(listing.token) }} token online or by UPI. It
									counts towards your first rent.</span
								>
							</span>
						</label>
						<!-- people leave this empty; bots fill it in -->
						<input
							v-model="form.website"
							class="hidden"
							tabindex="-1"
							autocomplete="off"
							aria-hidden="true"
						/>
						<p v-if="formError" class="text-sm text-rose-600">{{ formError }}</p>
						<Button
							variant="primary"
							size="lg"
							type="submit"
							class="w-full"
							:loading="sending"
							>{{ form.book ? "Continue to payment" : "Send" }}</Button
						>
						<div
							v-if="listing.phone"
							class="flex gap-2 border-t border-slate-100 pt-4"
						>
							<Button
								size="sm"
								class="flex-1"
								:icon="Phone"
								:href="`tel:${listing.phone}`"
								>Call</Button
							>
							<Button
								size="sm"
								class="flex-1"
								:icon="MessageCircle"
								:href="whatsapp"
								target="_blank"
								>WhatsApp</Button
							>
						</div>
					</form>
				</aside>
			</main>
		</template>
	</div>
</template>

<script setup>
import {
	Check,
	ChevronLeft,
	CircleCheck,
	CreditCard,
	MapPin,
	MessageCircle,
	Phone,
	Smartphone,
} from "lucide-vue-next";
import { computed, nextTick, onMounted, reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import { money } from "@/utils";

const METHOD = "rent_management.leads.";
const slug = decodeURIComponent(window.location.pathname.replace(/^\/stay\/?/, "").split("/")[0]);
const params = new URLSearchParams(window.location.search);
// a tenant's referral link: kept while they look around the buildings
const referralCode = (() => {
	try {
		if (params.get("ref")) sessionStorage.setItem("ref", params.get("ref"));
		return params.get("ref") || sessionStorage.getItem("ref");
	} catch {
		return params.get("ref");
	}
})();

const loading = ref(true);
const error = ref("");
const listing = ref(null);
const building = computed(() => (slug ? listing.value?.buildings[0] : null));
const booking = ref(null);
const bookingCard = ref(null);
const formCard = ref(null);

const totalFree = computed(() =>
	(listing.value?.buildings || []).reduce((sum, b) => sum + b.free_beds, 0)
);
const cities = computed(
	() =>
		[...new Set((listing.value?.buildings || []).map((b) => b.city).filter(Boolean))].join(
			", "
		) || "town"
);

function tags(b) {
	return [
		{ Men: "For men", Women: "For women", Anyone: "Co-living" }[b.listing_for],
		b.food_included ? "Food included" : null,
	].filter(Boolean);
}

const form = reactive({
	name: "",
	mobile_no: "",
	email_id: "",
	room_type: "",
	move_in_date: "",
	message: "",
	book: false,
	website: "",
});
const wantsVisit = ref(false);
const visitDay = ref("");
const visitTime = ref("11:00");
const visitTimes = [
	"10:00",
	"11:00",
	"12:00",
	"14:00",
	"15:00",
	"16:00",
	"17:00",
	"18:00",
	"19:00",
];

const chosenType = computed(() =>
	building.value?.room_types.find((r) => r.type === form.room_type)
);
const canBook = computed(() => listing.value?.token > 0 && chosenType.value?.free > 0);

const whatsapp = computed(() => {
	const digits = (listing.value?.phone || "").replace(/[^\d]/g, "");
	const number = digits.length === 10 ? `91${digits}` : digits;
	const text = `Hello, I'm interested in a bed at ${building.value?.name}.`;
	return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
});

function when(value) {
	return new Intl.DateTimeFormat("en-IN", {
		weekday: "short",
		day: "numeric",
		month: "short",
		hour: "numeric",
		minute: "2-digit",
	}).format(new Date(value.replace(" ", "T")));
}

async function choose(rt, book) {
	form.room_type = rt.type;
	form.book = book && rt.free > 0;
	await nextTick();
	formCard.value?.scrollIntoView({ behavior: "smooth", block: "start" });
}

const sending = ref(false);
const formError = ref("");
async function submit() {
	sending.value = true;
	formError.value = "";
	try {
		const result = await post(METHOD + "enquire", {
			building: slug,
			...form,
			book: form.book && canBook.value ? 1 : 0,
			ref: referralCode,
			visit_on:
				wantsVisit.value && visitDay.value
					? `${visitDay.value} ${visitTime.value}:00`
					: null,
		});
		const url = new URL(window.location.href);
		url.searchParams.set("booking", result.key);
		window.history.replaceState(null, "", url);
		await loadBooking(result.key);
		Object.assign(form, { message: "", book: false });
		wantsVisit.value = false;
		if (result.booking && booking.value?.online && !booking.value?.upi_link) await payOnline();
	} catch (e) {
		formError.value = e.message;
	} finally {
		sending.value = false;
	}
}

async function loadBooking(key) {
	try {
		booking.value = await get(METHOD + "get_booking", { key });
		await nextTick();
		bookingCard.value?.scrollIntoView({ behavior: "smooth", block: "start" });
	} catch {
		booking.value = null;
	}
}

// the key is put in the address after enquiring, so it can be shared and reopened
const bookingKey = () => new URL(window.location.href).searchParams.get("booking");

const paying = ref(false);
async function payOnline() {
	paying.value = true;
	try {
		window.location.href = await post(METHOD + "pay_token", { key: bookingKey() });
	} catch (e) {
		formError.value = e.message;
		paying.value = false;
	}
}

const reference = ref("");
const reporting = ref(false);
async function reportPaid() {
	reporting.value = true;
	try {
		booking.value = await post(METHOD + "report_token", {
			key: bookingKey(),
			reference: reference.value,
		});
	} catch (e) {
		formError.value = e.message;
	} finally {
		reporting.value = false;
	}
}

onMounted(async () => {
	try {
		listing.value = await get(METHOD + "get_listing", {
			...(slug && { building: slug }),
			...(referralCode && { ref: referralCode }),
		});
		if (params.get("booking")) await loadBooking(params.get("booking"));
		const type = params.get("room");
		if (type && building.value?.room_types.some((r) => r.type === type)) form.room_type = type;
	} catch (e) {
		error.value = e.message;
	} finally {
		loading.value = false;
	}
});
</script>
