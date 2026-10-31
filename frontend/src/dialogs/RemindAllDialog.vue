<template>
	<Modal
		open
		title="Remind everyone who owes rent"
		:subtitle="subtitle"
		width="lg"
		@close="$emit('close')"
	>
		<div v-if="!data" class="space-y-2"><Skeleton v-for="i in 5" :key="i" class="h-10" /></div>

		<!-- the result -->
		<div v-else-if="result" class="space-y-3 py-2 text-sm">
			<div class="flex items-center gap-3">
				<span
					class="grid size-11 place-items-center rounded-full bg-emerald-50 text-emerald-600"
					><CircleCheck class="size-6"
				/></span>
				<p class="text-lg font-semibold">
					{{ result.sent }} reminder{{ result.sent === 1 ? "" : "s" }} sent
				</p>
			</div>
			<div v-if="result.skipped.length" class="rounded-xl bg-slate-50 p-3">
				<p class="font-medium">{{ result.skipped.length }} skipped</p>
				<p v-for="(s, i) in result.skipped" :key="i" class="text-slate-500">
					{{ s.tenant_name }}: {{ s.why }}
				</p>
			</div>
			<div v-if="result.failed.length" class="rounded-xl bg-rose-50 p-3 text-rose-800">
				<p class="font-medium">{{ result.failed.length }} not sent</p>
				<p v-for="(s, i) in result.failed" :key="i">{{ s.tenant_name }}: {{ s.why }}</p>
			</div>
		</div>

		<!-- nothing can be sent -->
		<div v-else-if="!data.channels.whatsapp && !data.channels.email" class="py-4 text-sm">
			<p class="font-medium">WhatsApp and email are both off.</p>
			<p class="mt-1 text-slate-500">
				Turn on reminders by WhatsApp or email in
				<RouterLink to="/settings" class="text-brand-600" @click="$emit('close')"
					>Settings</RouterLink
				>
				to send them from here.
			</p>
		</div>

		<div v-else-if="!data.rows.length" class="py-6 text-center text-sm text-slate-500">
			Nobody owes rent right now.
		</div>

		<!-- who will get one -->
		<template v-else>
			<div class="mb-3 flex flex-wrap items-center gap-2 text-sm">
				<button class="chip" @click="choose((r) => r.overdue)">Overdue</button>
				<button class="chip" @click="choose(() => true)">Everyone</button>
				<button class="chip" @click="choose(() => false)">Nobody</button>
				<span class="ml-auto text-xs text-slate-500">Sent by {{ channelText }}</span>
			</div>
			<ul
				class="max-h-[55vh] divide-y divide-slate-100 overflow-y-auto rounded-xl border border-slate-200"
			>
				<li v-for="r in data.rows" :key="r.invoice">
					<label
						class="flex items-center gap-3 px-4 py-2.5 text-sm"
						:class="!canSend(r) && 'opacity-60'"
					>
						<input
							v-model="chosen"
							type="checkbox"
							:value="r.invoice"
							:disabled="!canSend(r)"
							class="size-4 accent-brand-600"
						/>
						<div class="min-w-0 flex-1">
							<p class="font-medium">
								{{ r.tenant_name }}
								<span class="font-normal text-slate-500">· room {{ r.room }}</span>
							</p>
							<p
								class="text-xs"
								:class="r.overdue ? 'text-rose-600' : 'text-slate-500'"
							>
								{{ r.period
								}}<template v-if="r.bills > 1">
									and {{ r.bills - 1 }} more</template
								>
								·
								{{
									r.overdue
										? `${r.days_overdue} day${
												r.days_overdue === 1 ? "" : "s"
										  } overdue`
										: `due ${date(r.due_on)}`
								}}
							</p>
						</div>
						<div class="text-right">
							<p class="tabular font-semibold">{{ money(r.owed) }}</p>
							<p class="text-xs text-slate-400">
								{{
									r.reminded_today
										? "Reminded today"
										: r.reach.length
										? r.reach.join(" + ")
										: "No number or email"
								}}
							</p>
						</div>
					</label>
				</li>
			</ul>
		</template>

		<template #footer>
			<template
				v-if="
					data &&
					!result &&
					data.rows.length &&
					(data.channels.whatsapp || data.channels.email)
				"
			>
				<Button @click="$emit('close')">Cancel</Button>
				<Button
					variant="primary"
					:icon="Send"
					:loading="sending"
					:disabled="!chosen.length"
					@click="send"
					>Send {{ chosen.length }} reminder{{ chosen.length === 1 ? "" : "s" }}</Button
				>
			</template>
			<Button v-else variant="primary" @click="$emit('close')">Done</Button>
		</template>
	</Modal>
</template>

<script setup>
import { CircleCheck, Send } from "lucide-vue-next";
import { computed, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Modal from "@/components/Modal.vue";
import Skeleton from "@/components/Skeleton.vue";
import { bumpData, scope, toast } from "@/store";
import { date, money } from "@/utils";

defineEmits(["close"]);

const data = ref(null);
const chosen = ref([]);
const result = ref(null);
const sending = ref(false);

const canSend = (r) => r.reach.length && !r.reminded_today && !r.inactive;
function choose(pick) {
	chosen.value = data.value.rows.filter((r) => canSend(r) && pick(r)).map((r) => r.invoice);
}

get("get_reminder_list", scope())
	.then((d) => {
		data.value = d;
		choose((r) => r.overdue); // the overdue ones to start with
	})
	.catch((e) => toast(e.message, "error"));

const owed = computed(() => (data.value?.rows || []).reduce((s, r) => s + r.owed, 0));
const subtitle = computed(() => {
	const n = data.value?.rows.length || 0;
	return n ? `${n} tenant${n === 1 ? " owes" : "s owe"} ${money(owed.value)}` : "";
});
const channelText = computed(() =>
	[data.value?.channels.whatsapp && "WhatsApp", data.value?.channels.email && "email"]
		.filter(Boolean)
		.join(" and ")
);

async function send() {
	sending.value = true;
	try {
		result.value = await post("send_bulk_reminders", { invoices: chosen.value });
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		sending.value = false;
	}
}
</script>

<style scoped>
.chip {
	border-radius: 9999px;
	padding: 0.25rem 0.75rem;
	font-weight: 500;
	color: rgb(71 85 105);
	box-shadow: inset 0 0 0 1px rgb(226 232 240);
}
.chip:hover {
	background: rgb(248 250 252);
}
</style>
