<template>
	<div class="space-y-4">
		<div class="card p-5">
			<RouterLink to="/invoices" class="text-sm text-slate-500">← Bills</RouterLink>
			<h1 class="mt-1 text-lg font-semibold">Your statement</h1>
			<p class="text-sm text-slate-500">
				Every bill and payment, and your deposit. Download it as a PDF, or a no-dues
				certificate once nothing is owed.
			</p>
			<TenantStatement
				class="mt-4"
				:fetch="(args) => get(call('get_statement'), args)"
				:pdf-url="pdfUrl"
				:no-dues-url="`/api/method/${call('download_no_dues')}`"
				:today="me.today"
			/>
		</div>
	</div>
</template>

<script setup>
import { get } from "@/api";
import TenantStatement from "@/components/TenantStatement.vue";

import { call, me } from "../store";

const pdfUrl = (args) => `/api/method/${call("download_statement")}?${new URLSearchParams(args)}`;
</script>
