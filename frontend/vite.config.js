import { copyFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

const root = path.dirname(fileURLToPath(import.meta.url));
const appPath = path.resolve(root, "../rent_management");

// Frappe serves www/rent.html at /rent and www/tenant.html at /tenant, so the built
// pages are copied there.
function copyIndexToWww() {
	return {
		name: "copy-index-to-www",
		closeBundle() {
			mkdirSync(path.join(appPath, "www"), { recursive: true });
			for (const [page, route] of [
				["index.html", "rent.html"],
				["tenant.html", "tenant.html"],
				["signup.html", "signup.html"],
				["stay.html", "stay.html"],
			]) {
				copyFileSync(
					path.join(appPath, "public/frontend", page),
					path.join(appPath, "www", route)
				);
			}
		},
	};
}

export default defineConfig(({ command }) => ({
	base: command === "build" ? "/assets/rent_management/frontend/" : "/",
	plugins: [vue(), tailwindcss(), copyIndexToWww()],
	resolve: {
		alias: { "@": path.resolve(root, "src") },
	},
	build: {
		outDir: path.join(appPath, "public/frontend"),
		emptyOutDir: true,
		target: "es2020",
		rollupOptions: {
			input: {
				main: path.resolve(root, "index.html"),
				tenant: path.resolve(root, "tenant.html"), // the tenant app
				signup: path.resolve(root, "signup.html"), // self-serve signup on the control site
				stay: path.resolve(root, "stay.html"), // the public listing page
			},
		},
	},
	server: {
		port: 8080,
		// during `yarn dev`, send API and asset calls to the Frappe dev server
		proxy: {
			"^/(api|assets|files|private|login|logout|printview)": "http://localhost:8000",
		},
	},
}));
