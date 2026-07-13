import * as fs from "fs";
import * as path from "path";

const siteFile = path.resolve(__dirname, "../../.auth/site.txt");

export function writeSiteId(id: string): void {
  fs.mkdirSync(path.dirname(siteFile), { recursive: true });
  fs.writeFileSync(siteFile, id);
}

export function readSiteId(): string {
  const id = fs.readFileSync(siteFile, "utf-8").trim();
  if (!id) throw new Error("No site id captured yet (run 00-sites.spec.ts first)");
  return id;
}
