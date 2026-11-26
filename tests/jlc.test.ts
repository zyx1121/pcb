import { describe, expect, test } from "bun:test";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { SEARCH, datasheet, lookup, search, toPart, type Fetch } from "../src/jlc.ts";

const raw = {
  componentCode: "C25804",
  componentModelEn: "0603WAF1002T5E",
  componentSpecificationEn: "0603",
  componentLibraryType: "base",
  stockCount: 39856817,
  componentPrices: [{ startNumber: 20, productPrice: 0.0005 }],
  dataManualUrl: "https://www.lcsc.com/datasheet/C25804.pdf",
};

function fake(pages: Record<string, () => Response>): Fetch {
  return async (url) => {
    const page = pages[url];
    if (!page) return new Response("nope", { status: 404 });
    return page();
  };
}

const api = () => Response.json({ data: { componentPageInfo: { list: [raw, { ...raw, componentCode: "C25805" }] } } });

describe("parts", () => {
  test("kind follows the library type and the preferred flag", () => {
    expect(toPart(raw).kind).toBe("basic");
    expect(toPart({ ...raw, componentLibraryType: "expand" }).kind).toBe("extended");
    expect(toPart({ ...raw, componentLibraryType: "expand", preferredComponentFlag: true }).kind).toBe("preferred");
  });

  test("search posts the keyword and maps the list", async () => {
    let body = "";
    const f: Fetch = async (url, init) => {
      expect(url).toBe(SEARCH);
      body = String(init?.body);
      return api();
    };
    const parts = await search("10k 0603", 5, f);
    expect(JSON.parse(body)).toMatchObject({ keyword: "10k 0603", pageSize: 5 });
    expect(parts[0]).toMatchObject({ code: "C25804", stock: 39856817, package: "0603" });
  });

  test("lookup returns only an exact code", async () => {
    expect((await lookup("C25805", fake({ [SEARCH]: api })))?.code).toBe("C25805");
    expect(await lookup("C1", fake({ [SEARCH]: api }))).toBeNull();
  });
});

describe("datasheet", () => {
  test("follows the HTML page to the PDF", async () => {
    const dir = await mkdtemp(join(tmpdir(), "pcb-"));
    const pdf = "https://datasheet.lcsc.com/lcsc/abc.pdf";
    const f = fake({
      [SEARCH]: api,
      [raw.dataManualUrl]: () => new Response(`<html><a href="${pdf}">pdf</a></html>`),
      [pdf]: () => new Response("%PDF-1.7 " + "x".repeat(2000)),
    });
    const got = await datasheet("C25804", dir, f);
    expect(got.bytes).toBeGreaterThan(1000);
    expect((await readFile(got.path, "latin1")).startsWith("%PDF")).toBe(true);
  });

  test("fails with a reason when there is no PDF", async () => {
    const dir = await mkdtemp(join(tmpdir(), "pcb-"));
    const f = fake({ [SEARCH]: api, [raw.dataManualUrl]: () => new Response("<html>no link</html>") });
    await expect(datasheet("C25804", dir, f)).rejects.toThrow("no PDF");
  });
});
