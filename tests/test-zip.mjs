/**
 * The ZIP writer, CSV writer and filename slug.
 *
 * The important test is not that the bytes look right to us — it is that a
 * real unzipper accepts them. This writes an archive to disk and then has
 * Python's `zipfile` open it, list it, verify the CRCs and read the contents
 * back. A hand-rolled container format that only this code can read would be a
 * trap, and self-consistent tests would not catch it.
 *
 *   node tests/test-zip.mjs
 */

import { makeZip, crc32, slug, toCsv } from "../static/zip.js";
import { writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

let failures = 0;
function check(label, ok, detail = "") {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  — " + detail : ""}`);
  if (!ok) failures++;
}

console.log("\nzip writer");

/* ---------- CRC-32 against known values ---------- */
const enc = new TextEncoder();
let rawDeflate = false;
try {
  new CompressionStream("deflate-raw");
  rawDeflate = true;
} catch {
  // Older Node releases do not expose the browser's raw-deflate stream. The
  // production writer deliberately falls back to a valid stored ZIP there.
}
check("crc32 of empty input is 0", crc32(enc.encode("")) === 0);
check("crc32('123456789') is the standard check value",
      crc32(enc.encode("123456789")) === 0xcbf43926,
      "0x" + crc32(enc.encode("123456789")).toString(16));
check("crc32('a') is known", crc32(enc.encode("a")) === 0xe8b7be43);

/* ---------- slug ---------- */
check("slug strips punctuation", slug('Striking At King\'s: "Part 2"/3') === "striking-at-king-s-part-2-3",
      slug('Striking At King\'s: "Part 2"/3'));
check("slug folds accents rather than dropping letters",
      slug("No Pasarán") === "no-pasaran", slug("No Pasarán"));
check("slug never returns empty", slug("!!!") === "untitled");
check("slug truncates", slug("x".repeat(200)).length <= 60);

/* ---------- CSV ---------- */
const csv = toCsv(["a", "b"], [{ a: 'say "hi"', b: "one,two" }, { a: "line\nbreak", b: null }]);
check("csv quotes embedded quotes", csv.includes('"say ""hi"""'));
check("csv quotes commas", csv.includes('"one,two"'));
check("csv quotes newlines", csv.includes('"line\nbreak"'));
check("csv renders null as empty", csv.trimEnd().endsWith(","));

/* ---------- the archive itself, opened by a real unzipper ---------- */
const long = "the pause between two words is where the cut belongs. ".repeat(200);
const files = [
  { name: "README.md", data: "# Archive\n\nHello.\n" },
  { name: "transcripts/0142-made-by-labour.txt", data: long },
  { name: "tiny.txt", data: "x" },                       // too small to compress
  { name: "unicode.txt", data: "No Pasarán — Workers’ Revolt\n" },
];
const zip = await makeZip(files);
const buf = Buffer.from(await zip.arrayBuffer());

const dir = mkdtempSync(join(tmpdir(), "ziptest-"));
const path = join(dir, "out.zip");
writeFileSync(path, buf);

try {
  const py = `
import zipfile, json, sys
z = zipfile.ZipFile(sys.argv[1])
bad = z.testzip()
out = {
  "bad": bad,
  "names": z.namelist(),
  "readme": z.read("README.md").decode(),
  "unicode": z.read("unicode.txt").decode(),
  "long_ok": len(z.read("transcripts/0142-made-by-labour.txt").decode()),
  "methods": sorted({i.compress_type for i in z.infolist()}),
  "compressed_smaller": z.getinfo("transcripts/0142-made-by-labour.txt").compress_size
                        < z.getinfo("transcripts/0142-made-by-labour.txt").file_size,
}
print(json.dumps(out))
`;
  const res = JSON.parse(execFileSync("python3", ["-c", py, path], { encoding: "utf8" }));

  check("a real unzipper opens it and every CRC checks out", res.bad === null,
        res.bad ? "corrupt entry: " + res.bad : "");
  check("all four entries are present", res.names.length === 4);
  check("nested paths survive",
        res.names.includes("transcripts/0142-made-by-labour.txt"));
  check("contents come back byte-for-byte", res.readme === "# Archive\n\nHello.\n");
  check("UTF-8 filenames and contents survive",
        res.unicode === "No Pasarán — Workers’ Revolt\n");
  check("a 10 KB file round-trips whole", res.long_ok === long.length);
  check(rawDeflate ? "large entries are deflated"
                   : "raw-deflate unavailable: entries use the stored fallback",
        rawDeflate ? res.methods.includes(8) : res.methods.includes(0));
  check("compression makes entries smaller when the runtime supports it",
        !rawDeflate || res.compressed_smaller === true,
        rawDeflate ? "" : "raw-deflate unavailable in this Node runtime");

  /* Determinism: the same input twice must give the same bytes, or two
     exports of unchanged data cannot be compared. */
  const again = Buffer.from(await (await makeZip(files)).arrayBuffer());
  check("the same data produces byte-identical archives", buf.equals(again));

  /* Stored mode must still be a valid archive. */
  const storedPath = join(dir, "stored.zip");
  writeFileSync(storedPath, Buffer.from(await (await makeZip(files, { compress: false })).arrayBuffer()));
  const res2 = JSON.parse(execFileSync("python3", ["-c", py, storedPath], { encoding: "utf8" }));
  check("uncompressed archives are valid too", res2.bad === null && res2.methods.join() === "0");
} finally {
  rmSync(dir, { recursive: true, force: true });
}

console.log(failures ? `\n${failures} failed` : "\nall passed");
process.exit(failures ? 1 : 0);
