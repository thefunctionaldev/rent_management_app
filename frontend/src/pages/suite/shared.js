import { get, post } from "@/api";
export const method = (name) => `rent_management.suite.${name}`;
export const read = (name, args) => get(method(name), args);
export const write = (name, args) => post(method(name), args);
export const download = (doctype, name, field) =>
	`/api/method/${method("files.download")}?${new URLSearchParams({ doctype, name, field })}`;
export async function upload(doctype, name, field, file) {
	if (!file) return;
	if (file.size > 5 * 1024 * 1024) throw new Error("Files must be smaller than 5 MB.");
	const data = await new Promise((resolve, reject) => {
		const r = new FileReader();
		r.onload = () => resolve(r.result);
		r.onerror = reject;
		r.readAsDataURL(file);
	});
	return write("files.upload", { doctype, name, field, filename: file.name, data });
}
export const title = (key) => key.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
