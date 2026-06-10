/**
 * Standalone sanity test for lib/taxonomyShading (no test runner configured in
 * this repo). Run with:  npx tsx _shading.test.mts
 */
import assert from "node:assert";
import {
  levenshtein,
  distanceLevel,
  columnReference,
  shadeColumn,
  computeShading,
  SHADE_PALETTE,
} from "./lib/taxonomyShading.ts";
import type { TaxonomyRow } from "./lib/types.ts";

let n = 0;
const ok = (c: boolean, m: string) => {
  assert.ok(c, m);
  n++;
};
const lvl = (a: string, b: string) => distanceLevel(levenshtein(a, b));

// edit distance
ok(levenshtein("muscaria", "muscaria") === 0, "identical = 0");
ok(levenshtein("cat", "bat") === 1, "one substitution = 1");
ok(levenshtein("", "abc") === 3, "empty vs abc = 3");

// buckets: 0 white, 1 light, 2-5 mid, 6-7 dark, 8+ darkest
ok(
  distanceLevel(0) === 0 &&
    distanceLevel(1) === 1 &&
    distanceLevel(2) === 2 &&
    distanceLevel(5) === 2 &&
    distanceLevel(6) === 3 &&
    distanceLevel(7) === 3 &&
    distanceLevel(8) === 4,
  "bucket boundaries",
);

const rows: TaxonomyRow[] = [
  { source: "GBIF", synonym_count: 0, Family: "Amanitaceae", Genus: "Amanita", Species: "muscaria" },
  { source: "symbiota_mycoportal", synonym_count: 0, Family: "Amanitaceae", Genus: "Amanita", Species: "muscaria" },
  { source: "mushroomobs", synonym_count: 0, Family: "Pluteaceae", Genus: "Amanita", Species: "muscaria" },
];

// reference resolution
ok(columnReference("Genus", rows, "Amanita muscaria") === "Amanita", "genus ref = query");
ok(columnReference("Species", rows, "Amanita muscaria") === "muscaria", "species ref = query");
ok(columnReference("Family", rows, "Amanita muscaria") === "Amanitaceae", "family ref = GBIF");
ok(columnReference("Family", rows.slice(1), "x") === "Amanitaceae", "family ref fallback = first visible");

// one differing value -> blue gradient
const fam = shadeColumn(rows, "Family", "Amanitaceae");
ok(fam.get("GBIF") === null && fam.get("symbiota_mycoportal") === null, "matching cells stay white");
ok(
  fam.get("mushroomobs")!.backgroundColor ===
    SHADE_PALETTE.blue[lvl("pluteaceae", "amanitaceae")].backgroundColor,
  "single differing value -> blue",
);

// two+ differing values -> orange gradient
const rows2: TaxonomyRow[] = [
  { source: "GBIF", synonym_count: 0, Family: "Amanitaceae" },
  { source: "b", synonym_count: 0, Family: "Pluteaceae" },
  { source: "c", synonym_count: 0, Family: "Strophariaceae" },
];
const fam2 = shadeColumn(rows2, "Family", "Amanitaceae");
ok(fam2.get("GBIF") === null, "reference stays white");
ok(
  fam2.get("b")!.backgroundColor ===
    SHADE_PALETTE.orange[lvl("pluteaceae", "amanitaceae")].backgroundColor,
  "two+ differing values -> orange (b)",
);
ok(
  fam2.get("c")!.backgroundColor ===
    SHADE_PALETTE.orange[lvl("strophariaceae", "amanitaceae")].backgroundColor,
  "two+ differing values -> orange (c)",
);

// genus differing from the query is shaded even for GBIF
const rows3: TaxonomyRow[] = [{ source: "GBIF", synonym_count: 0, Genus: "Amanitaria" }];
const g = shadeColumn(rows3, "Genus", columnReference("Genus", rows3, "Amanita muscaria"));
ok(
  g.get("GBIF") !== null &&
    g.get("GBIF")!.backgroundColor === SHADE_PALETTE.blue[lvl("amanitaria", "amanita")].backgroundColor,
  "GBIF genus differing from query -> blue",
);

// empty cells stay white
const rows4: TaxonomyRow[] = [
  { source: "GBIF", synonym_count: 0, Family: "Amanitaceae" },
  { source: "b", synonym_count: 0, Family: "" },
];
ok(shadeColumn(rows4, "Family", "Amanitaceae").get("b") === null, "empty cell stays white");

// full-table shape
const all = computeShading(rows, ["Family", "Genus", "Species"], "Amanita muscaria");
ok(all.has("Family") && all.has("Genus") && all.has("Species"), "computeShading covers all ranks");

console.log(`ALL ${n} ASSERTIONS PASSED`);
