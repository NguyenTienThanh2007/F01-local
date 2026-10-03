import { readFile, writeFile } from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";

const source = new URL("../openapi.json", import.meta.url);
const destination = new URL("../src/schema.ts", import.meta.url);
const schema = astToString(await openapiTS(source));
const content = "// Generated from FastAPI OpenAPI. Run pnpm api:generate; do not edit.\n" + schema;
if (process.argv.includes("--check")) {
  if (await readFile(destination, "utf8") !== content) {
    throw new Error("TypeScript client drift: run pnpm api:generate.");
  }
  console.log("Generated TypeScript contract is current.");
} else {
  await writeFile(destination, content);
  console.log("Generated TypeScript contract.");
}
