import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createServer } from "vite";
import { createSSRApp, h } from "vue";
import { renderToString } from "@vue/server-renderer";
let server, EditForm, i18n, language, t;
before(async () => {
  server = await createServer({
    server: { middlewareMode: true },
    appType: "custom",
  });
  EditForm = (await server.ssrLoadModule("/src/pages/suite/EditForm.vue"))
    .default;
  ({ i18n, language, t } = await server.ssrLoadModule("/src/i18n.js"));
});
after(async () => {
  await server?.close();
});
test("editing dialog is visible and escapes user input", async () => {
  language.value = "en";
  const ctx = {};
  const app = createSSRApp({
    render: () =>
      h(EditForm, {
        title: "New work order",
        fields: [{ key: "subject", required: true }],
        initial: { subject: "<script>unsafe</script>" },
        save: async () => {},
      }),
  }).use(i18n);
  await renderToString(app, ctx);
  assert.match(ctx.teleports.body, /role="dialog"/);
  assert.match(ctx.teleports.body, /New work order/);
  assert.match(ctx.teleports.body, /&lt;script&gt;unsafe&lt;\/script&gt;/);
  assert.doesNotMatch(ctx.teleports.body, /<script>unsafe/);
});
test("Hindi changes UI labels while preserving submitted option values", async () => {
  language.value = "hi";
  const ctx = {};
  await renderToString(
    createSSRApp({
      render: () =>
        h(EditForm, {
          title: "Record payment",
          fields: [
            { key: "mode_of_payment", options: ["Cash", "Bank Transfer"] },
          ],
          initial: { mode_of_payment: "Cash" },
          save: async () => {},
        }),
    }).use(i18n),
    ctx
  );
  assert.match(ctx.teleports.body, /भुगतान दर्ज करें/);
  assert.match(ctx.teleports.body, /value="Cash"/);
  assert.match(ctx.teleports.body, /नकद/);
  assert.match(ctx.teleports.body, /सहेजें/);
});
test("unknown user content is preserved and English can be restored", () => {
  language.value = "hi";
  assert.equal(t("Building Shanti"), "Building Shanti");
  assert.equal(t("Save"), "सहेजें");
  language.value = "en";
  assert.equal(t("Save"), "Save");
});
