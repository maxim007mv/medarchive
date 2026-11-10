import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Fixture paths and expectations come from qa/fixtures/manifest.json (QA-01), never from literals.

export type DocumentType = "analysis" | "conclusion" | "other";

export interface SourceFixture {
  path: string;
  fileName: string;
  sha256: string;
  sizeBytes: number;
  title: string;
  type: DocumentType;
  documentDate: string | null;
  expectedOrder: number;
}

export interface GeneratedFixture {
  path: string;
  fileName: string;
  sha256: string;
  sizeBytes: number;
  expectedResult: string;
  testCases: string[];
}

interface RawManifest {
  upload_limit_bytes: number;
  sources: {
    path: string;
    sha256: string;
    size_bytes: number;
    title: string;
    type: DocumentType;
    document_date: string | null;
    expected_order: number;
  }[];
  generated: {
    name: string;
    sha256: string;
    size_bytes: number;
    expected_result: string;
    test_cases: string[];
  }[];
}

const repoRoot = fileURLToPath(new URL("../..", import.meta.url));
const raw = JSON.parse(
  readFileSync(`${repoRoot}qa/fixtures/manifest.json`, "utf8"),
) as RawManifest;

export const uploadLimitBytes = raw.upload_limit_bytes;

/** The six PDFs from the task, in file order 01..06 (upload order decides ties in sorting). */
export const sources: SourceFixture[] = raw.sources.map((source) => ({
  path: `${repoRoot}${source.path}`,
  fileName: source.path.split("/").at(-1) ?? source.path,
  sha256: source.sha256,
  sizeBytes: source.size_bytes,
  title: source.title,
  type: source.type,
  documentDate: source.document_date,
  expectedOrder: source.expected_order,
}));

/** Titles in the default list order (document date desc, undated last). */
export const titlesInDefaultOrder: string[] = [...sources]
  .sort((a, b) => a.expectedOrder - b.expectedOrder)
  .map((source) => source.title);

/** A generated fixture by file name; fails loudly when `make fixtures` has not been run. */
export function generatedFixture(name: string): GeneratedFixture {
  const entry = raw.generated.find((fixture) => fixture.name === name);
  if (!entry) throw new Error(`fixture ${name} is not in qa/fixtures/manifest.json`);
  const path = `${repoRoot}qa/fixtures/generated/${entry.name}`;
  if (!existsSync(path)) throw new Error(`${path} is missing: run \`make fixtures\``);
  return {
    path,
    fileName: entry.name,
    sha256: entry.sha256,
    sizeBytes: entry.size_bytes,
    expectedResult: entry.expected_result,
    testCases: entry.test_cases,
  };
}
