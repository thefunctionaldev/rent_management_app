<template>
	<div>
		<PageHeader
			title="Food"
			subtitle="What the kitchen cooks, the weekly menu and the cost per meal"
		>
			<div class="flex overflow-hidden rounded-lg ring-1 ring-slate-200">
				<button
					v-for="d in dayOptions"
					:key="d.value"
					class="px-3 py-2 text-sm font-medium transition"
					:class="
						day === d.value
							? 'bg-slate-900 text-white'
							: 'bg-white text-slate-600 hover:bg-slate-50'
					"
					@click="day = d.value"
				>
					{{ d.label }}
				</button>
			</div>
		</PageHeader>

		<div v-if="loading && !data" class="space-y-4">
			<Skeleton class="h-40" />
			<Skeleton class="h-72" />
		</div>
		<EmptyState
			v-else-if="!data?.buildings.length"
			:icon="UtensilsCrossed"
			title="No buildings serve food"
			description="Edit a building and tick Food included to plan meals and let tenants skip the ones they won't eat."
		/>

		<section v-for="b in data?.buildings || []" :key="b.name" class="mb-8 space-y-4">
			<h2 v-if="data.buildings.length > 1" class="text-sm font-semibold text-slate-700">
				{{ b.name }}
			</h2>
			<div class="grid gap-4 md:grid-cols-3">
				<div v-for="m in b.meals" :key="m.meal" class="card p-5">
					<div class="flex items-center justify-between">
						<p class="font-medium">{{ m.meal }}</p>
						<span class="text-xs text-slate-500">{{ m.time }}</span>
					</div>
					<p class="mt-3">
						<span class="tabular text-3xl font-semibold">{{ m.eating }}</span>
						<span class="text-sm text-slate-500">
							to cook for, of {{ m.expected }}</span
						>
					</p>
					<p v-if="b.today[m.meal]" class="mt-2 text-sm text-slate-600">
						{{ b.today[m.meal] }}
					</p>
					<div v-if="m.skipping.length" class="mt-3 flex flex-wrap gap-1.5">
						<span
							v-for="s in m.skipping"
							:key="s.tenant_name"
							class="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800"
							>{{ s.tenant_name }} · {{ s.room }}</span
						>
					</div>
					<p v-else class="mt-3 text-xs text-slate-400">Nobody is skipping</p>
				</div>
			</div>

			<div class="grid gap-4 lg:grid-cols-[1fr_18rem]">
				<div class="card">
					<div
						class="flex items-center justify-between border-b border-slate-100 px-5 py-4"
					>
						<div>
							<h3 class="font-semibold">Weekly menu</h3>
							<p class="text-xs text-slate-500">
								Tenants see it in the tenant app. They can skip a meal until
								{{ b.cutoff_hours }} hours before it.
							</p>
						</div>
						<Button
							size="sm"
							variant="primary"
							:loading="saving === b.name"
							@click="saveMenu(b)"
							>Save menu</Button
						>
					</div>
					<div class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead class="bg-slate-50/60">
								<tr>
									<th class="table-head w-28">Day</th>
									<th v-for="m in b.meals" :key="m.meal" class="table-head">
										{{ m.meal }}
									</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-slate-100">
								<tr
									v-for="d in days"
									:key="d"
									:class="d === data.weekday && 'bg-brand-50/40'"
								>
									<td class="table-cell font-medium">{{ d }}</td>
									<td v-for="m in b.meals" :key="m.meal" class="px-2 py-1.5">
										<input
											v-model="b.menu[d][m.meal]"
											class="input py-1.5 text-sm"
											placeholder="—"
										/>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="card space-y-3 p-5">
					<h3 class="font-semibold">Food cost · {{ b.costs.month }}</h3>
					<dl class="space-y-2 text-sm">
						<div class="flex justify-between">
							<dt class="text-slate-500">Food & groceries</dt>
							<dd class="tabular">{{ money(b.costs.spent) }}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-slate-500">Meals served</dt>
							<dd class="tabular">{{ b.costs.meals_served }}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-slate-500">Meals skipped</dt>
							<dd class="tabular">{{ b.costs.skipped }}</dd>
						</div>
						<div
							class="flex justify-between border-t border-slate-100 pt-2 font-medium"
						>
							<dt>Cost per meal</dt>
							<dd class="tabular">{{ money(b.costs.per_meal) }}</dd>
						</div>
						<div class="flex justify-between font-medium">
							<dt>Per tenant per month</dt>
							<dd class="tabular">{{ money(b.costs.per_tenant_month) }}</dd>
						</div>
					</dl>
					<p class="text-xs text-slate-500">
						From expenses in <i>Food &amp; Groceries</i>. Skipped meals aren't cooked,
						so they lower the cost.
					</p>
				</div>
			</div>
		</section>
	</div>
</template>

<script setup>
import { UtensilsCrossed } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import { boot, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { money } from "@/utils";

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const addDays = (n) => {
	const d = new Date(`${boot.today}T00:00:00`);
	d.setDate(d.getDate() + n);
	return d.toLocaleDateString("en-CA"); // YYYY-MM-DD
};
const dayOptions = computed(() => [
	{ value: boot.today, label: "Today" },
	{ value: addDays(1), label: "Tomorrow" },
]);
const day = ref(boot.today);
const { data, loading, reload } = useResource(() =>
	get("get_food", { day: day.value, ...scope() })
);
watch(day, reload);

const saving = ref(null);
async function saveMenu(b) {
	saving.value = b.name;
	try {
		await post("save_menu", { property: b.name, menu: b.menu });
		toast("Menu saved");
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = null;
	}
}
</script>
