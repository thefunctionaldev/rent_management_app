<template>
	<div class="space-y-4">
		<div class="card p-5">
			<RouterLink to="/profile" class="text-sm text-slate-500">← Profile</RouterLink>
			<h1 class="mt-1 text-lg font-semibold">My documents</h1>
			<p class="text-sm text-slate-500">
				Your ID and papers, kept safely with your landlord. Only you and the management can
				see them.
			</p>
		</div>
		<div class="card">
			<TenantDocuments
				tenant-app
				intro="Add your PAN, passport, visa, offer letter or college ID."
			/>
		</div>
	</div>
</template>

<script setup>
import TenantDocuments from "@/components/TenantDocuments.vue";
</script>
