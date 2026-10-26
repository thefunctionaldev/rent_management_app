<template>
	<div class="space-y-4">
		<div class="card p-5">
			<div class="flex items-center gap-3">
				<Avatar :name="me.full_name" size="lg" />
				<div>
					<p class="text-lg font-semibold">{{ me.full_name }}</p>
					<p class="text-sm text-slate-500">{{ me.email }}</p>
					<p v-if="me.mobile_no" class="text-sm text-slate-500">{{ me.mobile_no }}</p>
				</div>
			</div>
			<p class="mt-3 text-xs text-slate-400">To change your details, ask your landlord.</p>
		</div>

		<div v-if="stay" class="card p-5">
			<h2 class="font-semibold">Your agreement</h2>
			<dl class="mt-3 space-y-2 text-sm">
				<div class="flex justify-between">
					<dt class="text-slate-500">Moved in</dt>
					<dd>{{ date(stay.allotment_date) }}</dd>
				</div>
				<div v-if="stay.agreement_end_date" class="flex justify-between">
					<dt class="text-slate-500">Agreement until</dt>
					<dd>{{ date(stay.agreement_end_date) }}</dd>
				</div>
				<div class="flex justify-between">
					<dt class="text-slate-500">Notice period</dt>
					<dd>{{ stay.notice_period_days || 0 }} days</dd>
				</div>
			</dl>
			<Button
				class="mt-4 w-full"
				:icon="FileText"
				href="/api/method/rent_management.portal.download_agreement"
				>Download agreement (PDF)</Button
			>

			<div class="mt-5 border-t border-slate-100 pt-4">
				<p
					v-if="stay.expected_vacate_date"
					class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800"
				>
					You gave notice on {{ date(stay.notice_given_on) }} and move out on
					{{ date(stay.expected_vacate_date) }}.
				</p>
				<template v-else>
					<p class="text-sm font-medium">Moving out?</p>
					<p class="text-sm text-slate-500">
						Give {{ stay.notice_period_days || 0 }} days' notice. Your landlord is told
						right away.
					</p>
					<div class="mt-3 flex gap-2">
						<input v-model="vacateDate" type="date" class="input" :min="me.today" />
						<Button :loading="giving" @click="giveNotice">Give notice</Button>
					</div>
				</template>
			</div>
		</div>

		<Button variant="ghost" class="w-full" :icon="LogOut" href="/logout">Log out</Button>
	</div>
</template>

<script setup>
import { FileText, LogOut } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { get, post } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import { toast } from "@/store";
import { useResource } from "@/useResource";
import { date } from "@/utils";

import { call, me } from "../store";

const { data, reload } = useResource(() => get(call("get_home")));
const stay = computed(() => data.value?.stay);

const vacateDate = ref("");
watch(
	stay,
	(s) => {
		if (!s || vacateDate.value) return;
		const d = new Date(`${me.today}T00:00:00`);
		d.setDate(d.getDate() + (s.notice_period_days || 0));
		vacateDate.value = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
			.toISOString()
			.slice(0, 10);
	},
	{ immediate: true }
);

const giving = ref(false);
async function giveNotice() {
	if (!window.confirm(`Give notice to move out on ${date(vacateDate.value)}?`)) return;
	giving.value = true;
	try {
		await post(call("give_notice"), { vacate_date: vacateDate.value });
		toast("Notice sent to your landlord");
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		giving.value = false;
	}
}
</script>
