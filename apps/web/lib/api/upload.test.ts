import { afterEach, describe, expect, test, vi } from "vitest";

import { NetworkError } from "./errors";
import { checkPdfFile, MAX_UPLOAD_BYTES, postToStorage, StorageRejectedError } from "./upload";

const pdf = (name = "01.pdf", size?: number) => {
  const content = new Uint8Array(size ?? 16);
  content.set(new TextEncoder().encode("%PDF-1.4"));
  return new File([content], name, { type: "application/pdf" });
};

describe("checkPdfFile (TC-015, TC-016)", () => {
  test("a real PDF passes", async () => {
    expect(await checkPdfFile(pdf())).toBeNull();
  });

  test("a PNG renamed to .pdf is not a PDF", async () => {
    const png = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a])], "fake.pdf", {
      type: "application/pdf",
    });

    expect(await checkPdfFile(png)).toBe("not_pdf");
  });

  test("another MIME type is not a PDF", async () => {
    expect(await checkPdfFile(new File(["%PDF-1.4"], "a.png", { type: "image/png" }))).toBe(
      "not_pdf",
    );
  });

  test("an empty file is not a PDF", async () => {
    expect(await checkPdfFile(new File([], "empty.pdf", { type: "application/pdf" }))).toBe(
      "not_pdf",
    );
  });

  test("exactly 20 МБ passes, one byte more is too large", async () => {
    expect(await checkPdfFile(pdf("max.pdf", MAX_UPLOAD_BYTES))).toBeNull();
    expect(await checkPdfFile(pdf("big.pdf", MAX_UPLOAD_BYTES + 1))).toBe("file_too_large");
  });
});

class FakeXhr {
  static last: FakeXhr;
  upload: { onprogress?: (event: ProgressEvent) => void } = {};
  status = 0;
  sent?: FormData;
  url?: string;
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;
  constructor() {
    FakeXhr.last = this;
  }
  open(_method: string, url: string) {
    this.url = url;
  }
  send(body: FormData) {
    this.sent = body;
  }
  abort() {
    this.onabort?.();
  }
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total } as ProgressEvent);
  }
}

describe("postToStorage", () => {
  afterEach(() => vi.unstubAllGlobals());

  const upload = {
    url: "http://storage/ma-quarantine",
    fields: { key: "q/1.bin", policy: "p", "x-amz-signature": "s" },
  };

  test("sends the policy fields first and the file last, reporting progress", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const progress: number[] = [];
    const done = postToStorage(
      upload,
      pdf(),
      (p) => progress.push(p),
      new AbortController().signal,
    );

    FakeXhr.last.progress(62, 100);
    FakeXhr.last.status = 204;
    FakeXhr.last.onload?.();
    await done;

    expect(FakeXhr.last.url).toBe(upload.url);
    expect([...FakeXhr.last.sent!.keys()]).toEqual(["key", "policy", "x-amz-signature", "file"]);
    expect(progress).toEqual([62]);
  });

  test("progress without a known total is ignored", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const progress: number[] = [];
    const done = postToStorage(
      upload,
      pdf(),
      (p) => progress.push(p),
      new AbortController().signal,
    );

    FakeXhr.last.upload.onprogress?.({
      lengthComputable: false,
      loaded: 5,
      total: 0,
    } as ProgressEvent);
    FakeXhr.last.status = 204;
    FakeXhr.last.onload?.();
    await done;

    expect(progress).toEqual([]);
  });

  test("aborting the signal aborts the transfer", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const controller = new AbortController();
    const done = postToStorage(upload, pdf(), () => undefined, controller.signal);

    controller.abort();

    await expect(done).rejects.toMatchObject({ name: "AbortError" });
  });

  test("a dropped connection is a NetworkError", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const done = postToStorage(upload, pdf(), () => undefined, new AbortController().signal);

    FakeXhr.last.onerror?.();

    await expect(done).rejects.toBeInstanceOf(NetworkError);
  });

  test("a rejected policy is reported with the storage status", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const done = postToStorage(upload, pdf(), () => undefined, new AbortController().signal);

    FakeXhr.last.status = 403;
    FakeXhr.last.onload?.();

    await expect(done).rejects.toEqual(new StorageRejectedError(403));
  });
});
