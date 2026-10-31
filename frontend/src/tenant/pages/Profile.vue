<template>
	<div class="space-y-4">
		<div class="card p-5">
			<div class="flex items-center gap-3">
				<Avatar :name="me.full_name" :image="me.picture" size="lg" />
				<div>
					<p class="text-lg font-semibold">{{ me.full_name }}</p>
					<p class="text-sm text-slate-500">{{ me.email }}</p>
					<p v-if="me.mobile_no" class="text-sm text-slate-500">{{ me.mobile_no }}</p>
				</div>
			</div>
			<div class="mt-4">
				<PictureInput
					:model-value="me.picture || ''"
					round
					buttons-only
					:name="me.full_name"
					@update:model-value="savePicture"
				/>
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

			<RouterLink
				to="/moving-out"
				class="mt-5 flex items-center gap-3 border-t border-slate-100 pt-4"
			>
				<div class="flex-1">
					<p class="text-sm font-medium">Moving out</p>
					<p class="text-sm text-slate-500">
						<template v-if="stay.expected_vacate_date"
							>On {{ date(stay.expected_vacate_date) }}. Your checklist and
							deposit</template
						><template v-else
							>Give notice, and see what happens to your deposit</template
						>
					</p>
				</div>
				<ChevronRight class="size-5 text-slate-400" />
			</RouterLink>
		</div>

		<RouterLink
			to="/documents"
			class="card flex items-center gap-3 p-4 transition hover:bg-slate-50"
		>
			<span class="grid size-10 place-items-center rounded-xl bg-slate-100 text-slate-600"
				><FolderOpen class="size-5"
			/></span>
			<div class="flex-1">
				<p class="font-medium">My documents</p>
				<p class="text-sm text-slate-500">ID, PAN, visa, offer letter</p>
			</div>
			<ChevronRight class="size-5 text-slate-400" />
		</RouterLink>

		<div v-if="!pwa.installed" class="card p-5">
			<InstallCard title="Put My Rent on your home screen" />
		</div>

		<Button variant="ghost" class="w-full" :icon="LogOut" @click="logout">Log out</Button>
	</div>
</template>

<script setup>
import { ChevronRight, FileText, FolderOpen, LogOut } from "lucide-vue-next";
import { computed } from "vue";

import { get, post } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import InstallCard from "@/components/InstallCard.vue";
import PictureInput from "@/components/PictureInput.vue";
import { forgetOfflineData, pwa } from "@/pwa";
import { toast } from "@/store";
import { useResource } from "@/useResource";
import { date } from "@/utils";

import { call, me } from "../store";

const { data } = useResource(() => get(call("get_home")));
const stay = computed(() => data.value?.stay);

async function logout() {
	await forgetOfflineData(); // the last bills loaded stay on the phone otherwise
	window.location.href = "/logout";
}

async function savePicture(picture) {
	try {
		me.picture = await post(call("update_picture"), { picture });
		toast(picture ? "Photo saved" : "Photo removed");
	} catch (e) {
		toast(e.message, "error");
	}
}
</script>
