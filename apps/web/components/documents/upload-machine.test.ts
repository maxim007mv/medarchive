import { describe, expect, test } from "vitest";

import {
  initialUploadState,
  isSaveInProgress,
  type UploadEvent,
  uploadReducer,
  type UploadState,
} from "./upload-machine";

const run = (...events: UploadEvent[]): UploadState =>
  events.reduce(uploadReducer, initialUploadState);

describe("upload state machine (FE-12)", () => {
  test("happy path: selected → uploading → verifying → ready → saving → saved", () => {
    const steps: [UploadEvent, string][] = [
      [{ type: "select" }, "selected"],
      [{ type: "progress", percent: 0 }, "uploading"],
      [{ type: "progress", percent: 62 }, "uploading"],
      [{ type: "progress", percent: 100 }, "verifying"],
      [{ type: "uploaded", uploadId: "u1" }, "ready"],
      [{ type: "save" }, "saving"],
      [{ type: "saved", documentId: "d1" }, "saved"],
    ];
    let state = initialUploadState;
    for (const [event, status] of steps) {
      state = uploadReducer(state, event);
      expect(state.phase.status).toBe(status);
    }
  });

  test("save pressed during the upload starts saving once the file is ready", () => {
    const waiting = run({ type: "select" }, { type: "progress", percent: 30 }, { type: "save" });
    expect(waiting.phase.status).toBe("uploading");
    expect(isSaveInProgress(waiting)).toBe(true);

    const ready = uploadReducer(waiting, { type: "uploaded", uploadId: "u1" });

    expect(ready.phase).toEqual({ status: "saving", uploadId: "u1" });
  });

  test("network break keeps the percent and the intention to save (TC-020)", () => {
    const state = run(
      { type: "select" },
      { type: "progress", percent: 62 },
      { type: "save" },
      { type: "failed", code: "network" },
    );

    expect(state.phase).toEqual({ status: "failed", code: "network", percent: 62, uploadId: null });
    expect(state.saveRequested).toBe(true);
  });

  test("retrying the upload after a break saves without another click", () => {
    const failed = run(
      { type: "select" },
      { type: "progress", percent: 62 },
      { type: "save" },
      { type: "failed", code: "network" },
    );

    const done = [
      { type: "select" },
      { type: "progress", percent: 100 },
      { type: "uploaded", uploadId: "u2" },
    ].reduce<UploadState>((state, event) => uploadReducer(state, event as UploadEvent), failed);

    expect(done.phase).toEqual({ status: "saving", uploadId: "u2" });
  });

  test("«Сохранить» pressed after the break is kept for the retry", () => {
    const failed = run(
      { type: "select" },
      { type: "progress", percent: 10 },
      { type: "failed", code: "network" },
    );

    const asked = uploadReducer(failed, { type: "save" });

    expect(asked.saveRequested).toBe(true);
    expect(
      uploadReducer(run({ type: "select" }, { type: "failed", code: "not_pdf" }), { type: "save" })
        .saveRequested,
    ).toBe(false);
  });

  test("a failed save keeps the upload, so retry saves the same upload_id", () => {
    const failed = run(
      { type: "select" },
      { type: "progress", percent: 100 },
      { type: "uploaded", uploadId: "u1" },
      { type: "save" },
      { type: "failed", code: "internal" },
    );
    expect(failed.phase).toMatchObject({ status: "failed", uploadId: "u1", percent: 100 });

    expect(uploadReducer(failed, { type: "retrySave" }).phase).toEqual({
      status: "saving",
      uploadId: "u1",
    });
  });

  test.each(["upload_expired", "upload_not_found"] as const)(
    "%s drops the upload so retry uploads again",
    (code) => {
      const state = run(
        { type: "select" },
        { type: "progress", percent: 100 },
        { type: "uploaded", uploadId: "u1" },
        { type: "save" },
        { type: "failed", code },
      );

      expect(state.phase).toMatchObject({ status: "failed", uploadId: null });
      expect(uploadReducer(state, { type: "retrySave" })).toBe(state);
    },
  );

  test.each(["not_pdf", "file_too_large", "pdf_unreadable", "pdf_encrypted"] as const)(
    "%s needs another file and cancels the pending save",
    (code) => {
      const state = run({ type: "select" }, { type: "save" }, { type: "failed", code });

      expect(state.phase).toMatchObject({ status: "failed", code, uploadId: null });
      expect(state.saveRequested).toBe(false);
    },
  );

  test("rejected fields return to ready with the same upload", () => {
    const state = run(
      { type: "select" },
      { type: "progress", percent: 100 },
      { type: "uploaded", uploadId: "u1" },
      { type: "save" },
      { type: "fieldsRejected" },
    );

    expect(state.phase).toEqual({ status: "ready", uploadId: "u1" });
    expect(isSaveInProgress(state)).toBe(false);
  });

  test("late progress after a failure is ignored", () => {
    const failed = run(
      { type: "select" },
      { type: "progress", percent: 40 },
      { type: "failed", code: "network" },
    );

    expect(uploadReducer(failed, { type: "progress", percent: 80 })).toBe(failed);
  });

  test("a second save while saving does nothing (TC-019)", () => {
    const saving = run(
      { type: "select" },
      { type: "progress", percent: 100 },
      { type: "uploaded", uploadId: "u1" },
      { type: "save" },
    );

    expect(uploadReducer(saving, { type: "save" })).toBe(saving);
  });

  test("saved is final", () => {
    const saved = run(
      { type: "select" },
      { type: "progress", percent: 100 },
      { type: "uploaded", uploadId: "u1" },
      { type: "save" },
      { type: "saved", documentId: "d1" },
    );

    expect(uploadReducer(saved, { type: "failed", code: "network" })).toBe(saved);
  });
});
