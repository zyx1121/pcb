/** JLCPCB's parts library and LCSC datasheets. Mirrors kit/pcbkit/jlc.py; keep the two in step. */
import { mkdir, stat, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

export const SEARCH = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList";

export type Fetch = (url: string, init?: RequestInit) => Promise<Response>;

export interface Part {
  code: string;
  mpn: string;
  maker: string;
  package: string;
  kind: "basic" | "preferred" | "extended";
  stock: number;
  description: string;
  prices: { from: number; usd: number }[];
  datasheet: string | null;
  url: string | null;
}

interface Raw {
  componentCode?: string;
  componentModelEn?: string;
  componentBrandEn?: string;
  componentSpecificationEn?: string;
  componentLibraryType?: string;
  preferredComponentFlag?: boolean;
  stockCount?: number;
  describe?: string;
  componentPrices?: { startNumber?: number; productPrice?: number }[];
  dataManualUrl?: string;
  lcscGoodsUrl?: string;
}

export function toPart(r: Raw): Part {
  return {
    code: r.componentCode ?? "",
    mpn: r.componentModelEn ?? "",
    maker: r.componentBrandEn ?? "",
    package: r.componentSpecificationEn ?? "",
    kind: r.componentLibraryType === "base" ? "basic" : r.preferredComponentFlag ? "preferred" : "extended",
    stock: Number(r.stockCount ?? 0),
    description: r.describe ?? "",
    prices: (r.componentPrices ?? []).map((p) => ({ from: Number(p.startNumber ?? 0), usd: Number(p.productPrice ?? 0) })),
    datasheet: r.dataManualUrl || null,
    url: r.lcscGoodsUrl || null,
  };
}

export async function search(keyword: string, limit: number, fetcher: Fetch = fetch): Promise<Part[]> {
  const res = await fetcher(SEARCH, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", "User-Agent": "Mozilla/5.0" },
    body: JSON.stringify({ currentPage: 1, pageSize: limit, keyword, searchSource: "search" }),
  });
  if (!res.ok) throw new Error(`JLCPCB answered ${res.status}`);
  const body = (await res.json()) as { data?: { componentPageInfo?: { list?: Raw[] } } };
  return (body.data?.componentPageInfo?.list ?? []).map(toPart);
}

export async function lookup(code: string, fetcher: Fetch = fetch): Promise<Part | null> {
  const hits = await search(code, 5, fetcher);
  return hits.find((p) => p.code === code) ?? null;
}

const PDF_LINK = /https?:\/\/[^"'\s]*datasheet\.lcsc\.com\/[^"'\s]+\.pdf/;

/** Save one part's datasheet as <dir>/<code>.pdf. LCSC's link answers with an HTML page whose
 * datasheet.lcsc.com link is the PDF. */
export async function datasheet(code: string, dir: string, fetcher: Fetch = fetch): Promise<{ path: string; bytes: number }> {
  const out = resolve(join(dir, `${code}.pdf`));
  const have = await stat(out).catch(() => null);
  if (have && have.size > 1000) return { path: out, bytes: have.size };
  const part = await lookup(code, fetcher);
  if (!part) throw new Error(`${code} is not in JLCPCB's library`);
  let url = part.datasheet;
  if (!url) throw new Error(`${code} has no datasheet link`);
  for (let hop = 0; hop < 2; hop++) {
    const res = await fetcher(url, { headers: { "User-Agent": "Mozilla/5.0" } });
    if (!res.ok) throw new Error(`datasheet link answered ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.subarray(0, 4).toString() === "%PDF") {
      await mkdir(dir, { recursive: true });
      await writeFile(out, buf);
      return { path: out, bytes: buf.length };
    }
    const m = buf.toString("latin1").match(PDF_LINK);
    if (!m) break;
    url = m[0];
  }
  throw new Error(`no PDF behind ${part.datasheet}`);
}
