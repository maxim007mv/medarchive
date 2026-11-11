import { api, call, csrfHeader, request } from "./client";
import { NetworkError } from "./errors";
import type { components } from "./schema";

export type Upload = components["schemas"]["Upload"];
export type DocumentCreate = components["schemas"]["DocumentCreate"];

export const PDF_MIME = "application/pdf";
/** 20 МБ in the catalogue; the storage policy enforces the same `content-length-range`. */
export const MAX_UPLOAD_BYTES = 20_971_520;
const PDF_SIGNATURE = "%PDF-";

export type FileCheckCode = "not_pdf" | "file_too_large";

/** Client check before any request (FE-12): type, first 5 bytes `%PDF-`, size. */
export async function checkPdfFile(file: File): Promise<FileCheckCode | null> {
  if (file.type !== "" && file.type !== PDF_MIME) return "not_pdf";
  if (file.size > MAX_UPLOAD_BYTES) return "file_too_large";
  const head = new Uint8Array(await file.slice(0, PDF_SIGNATURE.length).arrayBuffer());
  const signature = String.fromCharCode(...head);
  return signature === PDF_SIGNATURE ? null : "not_pdf";
}

export async function requestUpload(file: File, idempotencyKey: string): Promise<Upload> {
  return call(
    api.POST("/api/v1/uploads", {
      params: { header: { "Idempotency-Key": idempotencyKey, ...(await csrfHeader()) } },
      body: { original_name: file.name, size_bytes: file.size, content_type: PDF_MIME },
    }),
  );
}

export async function createDocument(body: DocumentCreate, idempotencyKey: string) {
  const { data, response } = await request(
    api.POST("/api/v1/documents", {
      params: { header: { "Idempotency-Key": idempotencyKey, ...(await csrfHeader()) } },
      body,
    }),
  );
  return { document: data, etag: response.headers.get("ETag") ?? "" };
}

export class StorageRejectedError extends Error {
  constructor(readonly status: number) {
    super(`storage rejected upload with ${status}`);
    this.name = "StorageRejectedError";
  }
}

/**
 * Presigned POST straight to the storage with progress (FE-12). The policy fields go first and the
 * file last: S3 ignores fields that come after the file.
 */
export function postToStorage(
  upload: Pick<Upload, "url" | "fields">,
  file: File,
  onProgress: (percent: number) => void,
  signal: AbortSignal,
): Promise<void> {
  const form = new FormData();
  for (const [name, value] of Object.entries(upload.fields)) form.append(name, value);
  form.append("file", file);
  const xhr = new XMLHttpRequest();
  const abortTransfer = () => xhr.abort();
  signal.addEventListener("abort", abortTransfer, { once: true });

  return new Promise<void>((resolve, reject) => {
    xhr.open("POST", upload.url);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.floor((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new StorageRejectedError(xhr.status));
    };
    xhr.onerror = () => reject(new NetworkError());
    xhr.onabort = () => reject(new DOMException("upload aborted", "AbortError"));
    xhr.send(form);
  }).finally(() => signal.removeEventListener("abort", abortTransfer));
}
