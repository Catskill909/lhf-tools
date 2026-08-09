/**
 * A ZIP writer, in about a page of code.
 *
 * No dependency, because this project has none and is not starting now. The
 * only part of ZIP that is genuinely hard is the compression, and the platform
 * already has it: CompressionStream("deflate-raw") produces exactly the bitstream
 * ZIP's method 8 expects. Everything else here is header layout.
 *
 * Where compression is unavailable the entry is *stored* instead. The archive
 * is still a valid ZIP that every tool can open — it is simply larger, which is
 * the right way for this to degrade.
 *
 * Timestamps are fixed rather than "now". A package built twice from unchanged
 * data should be byte-identical, so that two exports can be diffed and a backup
 * can be checked against its predecessor. The real date is in the filename and
 * in the README, where a person will look for it.
 */

const SIG_LOCAL = 0x04034b50;
const SIG_CENTRAL = 0x02014b50;
const SIG_EOCD = 0x06054b50;

// 1980-01-01 00:00:00, the earliest a DOS timestamp can express. Any constant
// would do; this one is conventionally "no meaningful date".
const DOS_TIME = 0;
const DOS_DATE = 33;

const enc = new TextEncoder();

/** CRC-32, table built once on first use. */
let TABLE = null;
function table() {
  if (TABLE) return TABLE;
  TABLE = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    TABLE[i] = c >>> 0;
  }
  return TABLE;
}

export function crc32(bytes) {
  const t = table();
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = t[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

async function deflate(bytes) {
  if (typeof CompressionStream === "undefined") return null;
  try {
    const cs = new CompressionStream("deflate-raw");
    const stream = new Blob([bytes]).stream().pipeThrough(cs);
    return new Uint8Array(await new Response(stream).arrayBuffer());
  } catch {
    return null;      // stored is always a valid fallback
  }
}

function bytesOf(data) {
  return typeof data === "string" ? enc.encode(data) : data;
}

/**
 * Build a ZIP.
 *
 * @param {{name: string, data: string|Uint8Array}[]} files
 * @param {{compress?: boolean}} opts
 * @returns {Promise<Blob>}
 */
export async function makeZip(files, opts = {}) {
  const compress = opts.compress !== false;
  const parts = [];        // body chunks, in order
  const central = [];      // central-directory records
  let offset = 0;

  for (const f of files) {
    const name = enc.encode(f.name);
    const raw = bytesOf(f.data);
    const sum = crc32(raw);

    let body = raw;
    let method = 0;
    if (compress && raw.length > 64) {
      const packed = await deflate(raw);
      // Compression that makes a file bigger is not compression. Short or
      // already-compressed entries land here and are stored instead.
      if (packed && packed.length < raw.length) {
        body = packed;
        method = 8;
      }
    }

    const local = new Uint8Array(30 + name.length);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, SIG_LOCAL, true);
    lv.setUint16(4, 20, true);          // version needed
    lv.setUint16(6, 0x0800, true);      // bit 11: the name is UTF-8
    lv.setUint16(8, method, true);
    lv.setUint16(10, DOS_TIME, true);
    lv.setUint16(12, DOS_DATE, true);
    lv.setUint32(14, sum, true);
    lv.setUint32(18, body.length, true);
    lv.setUint32(22, raw.length, true);
    lv.setUint16(26, name.length, true);
    lv.setUint16(28, 0, true);
    local.set(name, 30);

    parts.push(local, body);

    const cd = new Uint8Array(46 + name.length);
    const cv = new DataView(cd.buffer);
    cv.setUint32(0, SIG_CENTRAL, true);
    cv.setUint16(4, 20, true);          // version made by
    cv.setUint16(6, 20, true);          // version needed
    cv.setUint16(8, 0x0800, true);
    cv.setUint16(10, method, true);
    cv.setUint16(12, DOS_TIME, true);
    cv.setUint16(14, DOS_DATE, true);
    cv.setUint32(16, sum, true);
    cv.setUint32(20, body.length, true);
    cv.setUint32(24, raw.length, true);
    cv.setUint16(28, name.length, true);
    cv.setUint32(42, offset, true);     // where the local header starts
    cd.set(name, 46);
    central.push(cd);

    offset += local.length + body.length;
  }

  const cdSize = central.reduce((n, c) => n + c.length, 0);
  const end = new Uint8Array(22);
  const ev = new DataView(end.buffer);
  ev.setUint32(0, SIG_EOCD, true);
  ev.setUint16(8, files.length, true);
  ev.setUint16(10, files.length, true);
  ev.setUint32(12, cdSize, true);
  ev.setUint32(16, offset, true);

  return new Blob([...parts, ...central, end], { type: "application/zip" });
}

/**
 * A filename-safe slug. Titles carry quotes, colons, slashes and accents, and
 * a package that cannot be unzipped on Windows is not a backup.
 */
export function slug(text, max = 60) {
  return (text || "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")     // strip accents rather than drop letters
    .replace(/[^A-Za-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, max)
    .toLowerCase() || "untitled";
}

/** RFC 4180 CSV. Quote anything that could otherwise break a cell. */
export function toCsv(headers, rows) {
  const cell = v => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const lines = [headers.map(cell).join(",")];
  for (const r of rows) lines.push(headers.map(h => cell(r[h])).join(","));
  return lines.join("\r\n") + "\r\n";
}
