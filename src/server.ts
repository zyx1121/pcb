import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import manifest from "../plugin.json";
import { datasheet, lookup, search } from "./jlc.ts";

const server = new McpServer({ name: manifest.name, version: manifest.version });

function reply(data: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify({ data }) }], structuredContent: { data } };
}

function failure(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return {
    content: [{ type: "text" as const, text: JSON.stringify({ error: { code: "upstream_error", message } }) }],
    structuredContent: { error: { code: "upstream_error", message } },
    isError: true,
  };
}

const READ = { readOnlyHint: true, openWorldHint: true } as const;

server.registerTool(
  "jlc_search",
  {
    description:
      "Search JLCPCB's assembly parts library by keyword, value or part number (e.g. '10k 0603', 'AO3400A', 'C25804'). " +
      "Returns LCSC code, MPN, package, kind (basic = no loading fee, preferred = no fee on Economic, extended = fee per part type), stock, price breaks and the datasheet link. " +
      "Prefer basic parts for passives; check stock against boards x parts per board.",
    inputSchema: { keyword: z.string().min(1), limit: z.number().int().min(1).max(50).default(10) },
    annotations: READ,
  },
  async ({ keyword, limit }) => {
    try {
      return reply(await search(keyword, limit));
    } catch (e) {
      return failure(e);
    }
  },
);

server.registerTool(
  "jlc_part",
  {
    description: "Look up LCSC codes (C25804 ...) in JLCPCB's library: kind, stock, package, MPN, prices and datasheet link. Missing codes come back as null.",
    inputSchema: { codes: z.array(z.string().regex(/^C\d+$/)).min(1).max(40) },
    annotations: READ,
  },
  async ({ codes }) => {
    try {
      const out: Record<string, unknown> = {};
      for (const c of codes) out[c] = await lookup(c);
      return reply(out);
    } catch (e) {
      return failure(e);
    }
  },
);

server.registerTool(
  "datasheet_fetch",
  {
    description:
      "Download the datasheet PDF of an LCSC part into a folder on this machine as <code>.pdf (skipped when it is already there). " +
      "Read the PDF itself before using any value from it, and cite the page.",
    inputSchema: { code: z.string().regex(/^C\d+$/), dir: z.string().min(1).describe("Folder to save into, e.g. the project's datasheets/") },
    annotations: { readOnlyHint: false, openWorldHint: true, destructiveHint: false },
  },
  async ({ code, dir }) => {
    try {
      return reply(await datasheet(code, dir));
    } catch (e) {
      return failure(e);
    }
  },
);

await server.connect(new StdioServerTransport());
