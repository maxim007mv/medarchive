import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import type { APIRequestContext, APIResponse } from "@playwright/test";

import { sources, type DocumentType, type SourceFixture } from "./manifest";

/** Version of docs/policy.md the consent checkbox refers to. */
export const POLICY_VERSION = "2026-11-10";
export const SESSION_COOKIE = "__Host-ma_sid";

export interface DocumentInput {
  title: string;
  type: DocumentType;
  document_date: string | null;
  note?: string | null;
}

/** `Document` of openapi.yaml; tests read the fields they assert on. */
interface DocumentBody {
  id: string;
  [field: string]: unknown;
}

export type CreatedDocument = DocumentBody & { etag: string };

export interface Archive {
  workspaceId: string;
  accessKey: string;
  csrfToken: string;
  api: ArchiveApi;
}

/**
 * Fails with what a defect ticket needs: route, status, problem code and X-Request-Id.
 * Response bodies are not echoed: they may carry document titles (AGENTS.md, no PII in reports).
 */
export async function expectStatus(response: APIResponse, expected: number): Promise<void> {
  if (response.status() === expected) return;
  const url = new URL(response.url());
  let code = "-";
  if (response.headers()["content-type"]?.includes("json")) {
    const body = (await response.json().catch(() => ({}))) as { code?: string };
    code = body.code ?? "-";
  }
  throw new Error(
    `${url.pathname}: expected ${expected}, got ${response.status()} code=${code} ` +
      `request_id=${response.headers()["x-request-id"] ?? "-"}`,
  );
}

/** Creates an archive with accepted consent; the session cookie lands in `request`'s cookie jar. */
export async function createArchive(request: APIRequestContext): Promise<Archive> {
  const response = await request.post("/api/v1/workspaces", {
    headers: { "Idempotency-Key": randomUUID() },
    data: {
      consent: { policy_version: POLICY_VERSION, accepted: true },
      timezone: "Europe/Moscow",
    },
  });
  await expectStatus(response, 201);
  const body = (await response.json()) as {
    workspace: { id: string };
    access_key: string;
    csrf_token: string;
  };
  return {
    workspaceId: body.workspace.id,
    accessKey: body.access_key,
    csrfToken: body.csrf_token,
    api: new ArchiveApi(request, body.csrf_token),
  };
}

/** Black-box client of the contract in openapi.yaml, through the same origin as the browser. */
export class ArchiveApi {
  constructor(
    readonly request: APIRequestContext,
    readonly csrfToken: string,
  ) {}

  /** A mutating request with the CSRF token and a fresh Idempotency-Key unless one is given. */
  send(
    method: "POST" | "PATCH" | "DELETE",
    path: string,
    options: { data?: unknown; headers?: Record<string, string> } = {},
  ): Promise<APIResponse> {
    return this.request.fetch(path, {
      method,
      data: options.data,
      headers: {
        "X-CSRF-Token": this.csrfToken,
        "Idempotency-Key": randomUUID(),
        ...options.headers,
      },
    });
  }

  /** Presigned POST straight to storage, as the browser does; returns `upload_id`. */
  async upload(filePath: string, originalName: string): Promise<string> {
    const bytes = readFileSync(filePath);
    const created = await this.send("POST", "/api/v1/uploads", {
      data: { original_name: originalName, size_bytes: bytes.length, content_type: "application/pdf" },
    });
    await expectStatus(created, 201);
    const { upload_id, url, fields } = (await created.json()) as {
      upload_id: string;
      url: string;
      fields: Record<string, string>;
    };
    // The policy fields go first: S3 ignores everything after the `file` part.
    const stored = await this.request.post(url, {
      multipart: { ...fields, file: { name: originalName, mimeType: "application/pdf", buffer: bytes } },
    });
    if (stored.status() >= 300) throw new Error(`storage upload: ${stored.status()}`);
    return upload_id;
  }

  async createDocument(uploadId: string, input: DocumentInput): Promise<CreatedDocument> {
    const response = await this.send("POST", "/api/v1/documents", {
      data: { upload_id: uploadId, ...input },
    });
    await expectStatus(response, 201);
    const body = (await response.json()) as DocumentBody;
    return { ...body, etag: response.headers().etag ?? "" };
  }

  /** Uploads one of the six task PDFs with its title, type and date from the manifest. */
  async addSource(source: SourceFixture, overrides: Partial<DocumentInput> = {}): Promise<CreatedDocument> {
    const uploadId = await this.upload(source.path, source.fileName);
    return this.createDocument(uploadId, {
      title: source.title,
      type: source.type,
      document_date: source.documentDate,
      ...overrides,
    });
  }

  /** The seed of test-strategy.md, section 3: all six PDFs in file order. */
  async addAllSources(): Promise<CreatedDocument[]> {
    const created: CreatedDocument[] = [];
    for (const source of sources) created.push(await this.addSource(source));
    return created;
  }
}
