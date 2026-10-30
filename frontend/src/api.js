// Thin client for the whitelisted methods in rent_management/api.py

const APP_METHOD = "rent_management.api.";

export class ApiError extends Error {}

// sent with every call: a staff login for one building always asks for that building
// (endpoints that don't take an argument ignore it)
const fixedArgs = {};
export const setFixedArgs = (args) => Object.assign(fixedArgs, args);

function csrfToken() {
	const token = window.csrf_token;
	// the placeholder is left as-is when running under `yarn dev`
	return token && !token.startsWith("{{") ? token : "";
}

function errorMessage(data, response) {
	if (data._server_messages) {
		try {
			const messages = JSON.parse(data._server_messages).map((m) => JSON.parse(m).message);
			const text = messages.join("\n");
			const div = document.createElement("div");
			div.innerHTML = text;
			return div.textContent || text;
		} catch {
			// fall through to the other formats
		}
	}
	if (data.exception)
		return data.exception.split(":").slice(1).join(":").trim() || data.exception;
	if (data.message && typeof data.message === "string") return data.message;
	return response.statusText || "Something went wrong";
}

async function request(method, args = {}, httpMethod = "POST") {
	args = { ...args, ...fixedArgs };
	let url = `/api/method/${method.includes(".") ? method : APP_METHOD + method}`;
	const options = {
		method: httpMethod,
		credentials: "same-origin",
		headers: { Accept: "application/json", "X-Frappe-CSRF-Token": csrfToken() },
	};

	if (httpMethod === "GET") {
		const params = new URLSearchParams();
		for (const [key, value] of Object.entries(args)) {
			if (value === undefined || value === null || value === "") continue;
			params.set(key, typeof value === "object" ? JSON.stringify(value) : value);
		}
		if (params.size) url += `?${params}`;
	} else {
		options.headers["Content-Type"] = "application/json";
		options.body = JSON.stringify(args);
	}

	let response;
	try {
		response = await fetch(url, options);
	} catch {
		throw new ApiError(
			navigator.onLine
				? "Couldn't reach the server. Try again."
				: "You're offline. Try again when you have a signal."
		);
	}
	let data = {};
	try {
		data = await response.json();
	} catch {
		// non-JSON error page
	}

	if (response.status === 403 && data.session_expired) {
		window.location.href = `/login?redirect-to=${encodeURIComponent(
			window.location.pathname
		)}`;
	}
	if (!response.ok || data.exc_type) {
		throw new ApiError(errorMessage(data, response));
	}
	return data.message;
}

export const get = (method, args) => request(method, args, "GET");
export const post = (method, args) => request(method, args, "POST");
