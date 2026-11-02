import test from "node:test";
import assert from "node:assert/strict";
import { addDate, occupancyCell } from "../src/occupancy.js";
const bed = { room: { status: "Available" } };
const stay = {
	allotment_date: "2026-11-01",
	status: "Active",
	expected_vacate_date: "2026-11-10",
	tenant: "T1",
	tenant_name: "Asha",
};
test("notice never releases a bed until an actual vacate", () => {
	assert.equal(occupancyCell(bed, "2026-11-10", [stay]).notice, true);
	assert.equal(occupancyCell(bed, "2026-11-11", [stay]).tenant, "T1");
});
test("move-in and move-out are inclusive; future stays do not occupy earlier dates", () => {
	const s = { ...stay, status: "Vacated", vacate_date: "2026-11-10" };
	assert.equal(occupancyCell(bed, "2026-10-31", [s]).label, "Unallotted");
	assert.equal(occupancyCell(bed, "2026-11-01", [s]).tenant, "T1");
	assert.equal(occupancyCell(bed, "2026-11-10", [s]).tenant, "T1");
	assert.equal(occupancyCell(bed, "2026-11-11", [s]).label, "Unallotted");
});
test("overlaps are conflicts, and unavailable rooms never show unallotted", () => {
	assert.match(occupancyCell(bed, "2026-11-02", [stay, stay]).label, /Conflict/);
	for (const status of ["Reserved", "Under Renovation"])
		assert.equal(occupancyCell({ room: { status } }, "2026-11-02", []).label, status);
});
test("date arithmetic crosses leap day and year end without timezone drift", () => {
	assert.equal(addDate("2028-02-28", 1), "2028-02-29");
	assert.equal(addDate("2026-12-31", 1), "2027-01-01");
	assert.equal(addDate("", 1), "");
});
