import { randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

import { createArchive, expectStatus } from "../../support/archive";
import { generatedFixture, sources, titlesInDefaultOrder } from "../../support/manifest";

const [blood] = sources;

async function problemCode(response: { json(): Promise<unknown> }): Promise<string> {
  return ((await response.json()) as { code: string }).code;
}

test("TC-022 POST /documents without Idempotency-Key is 400", { tag: ["@b4", "@P0", "@TC-022"] }, async ({ request }) => {
  const { api } = await createArchive(request);
  const uploadId = await api.upload(blood.path, blood.fileName);

  const response = await request.post("/api/v1/documents", {
    headers: { "X-CSRF-Token": api.csrfToken },
    data: { upload_id: uploadId, title: blood.title, type: blood.type, document_date: blood.documentDate },
  });

  await expectStatus(response, 400);
  expect(await problemCode(response)).toBe("idempotency_key_missing");
});

test("TC-023 the same Idempotency-Key with another body is 422", { tag: ["@b4", "@P0", "@TC-023"] }, async ({ request }) => {
  const { api } = await createArchive(request);
  const uploadId = await api.upload(blood.path, blood.fileName);
  const key = randomUUID();
  const body = { upload_id: uploadId, title: blood.title, type: blood.type, document_date: blood.documentDate };

  await expectStatus(await api.send("POST", "/api/v1/documents", { data: body, headers: { "Idempotency-Key": key } }), 201);
  const reused = await api.send("POST", "/api/v1/documents", {
    data: { ...body, title: "Другое название" },
    headers: { "Idempotency-Key": key },
  });

  await expectStatus(reused, 422);
  expect(await problemCode(reused)).toBe("idempotency_key_reused");
});

test("TC-019 replay with the same key and body returns the stored answer", { tag: ["@b4", "@P0", "@TC-019"] }, async ({ request }) => {
  const { api } = await createArchive(request);
  const uploadId = await api.upload(blood.path, blood.fileName);
  const options = {
    data: { upload_id: uploadId, title: blood.title, type: blood.type, document_date: blood.documentDate },
    headers: { "Idempotency-Key": randomUUID() },
  };

  const first = await api.send("POST", "/api/v1/documents", options);
  const replay = await api.send("POST", "/api/v1/documents", options);

  await expectStatus(first, 201);
  await expectStatus(replay, 201);
  expect(replay.headers()["idempotent-replayed"]).toBe("true");
  expect(((await replay.json()) as { id: string }).id).toBe(((await first.json()) as { id: string }).id);
  const list = (await (await request.get("/api/v1/documents")).json()) as { total: number };
  expect(list.total).toBe(1);
});

test("TC-024 a Cyrillic file name is stored", { tag: ["@b4", "@P1", "@TC-024"] }, async ({ request }) => {
  const fixture = generatedFixture("cyrillic «имя» файла.pdf");
  const { api } = await createArchive(request);
  const uploadId = await api.upload(fixture.path, fixture.fileName);

  const created = await api.createDocument(uploadId, { title: blood.title, type: blood.type, document_date: null });

  expect((created.file as { original_name: string }).original_name).toBe(fixture.fileName);
});

test("TC-024 download sends the Cyrillic name as filename* in UTF-8", { tag: ["@b5", "@P1", "@TC-024"] }, async ({ request }) => {
  const fixture = generatedFixture("cyrillic «имя» файла.pdf");
  const { api } = await createArchive(request);
  const created = await api.createDocument(await api.upload(fixture.path, fixture.fileName), {
    title: blood.title,
    type: blood.type,
    document_date: null,
  });

  const response = await request.get(`/api/v1/documents/${created.id}/content?disposition=attachment`);

  await expectStatus(response, 200);
  expect(response.headers()["content-disposition"]).toContain(
    `filename*=UTF-8''${encodeURIComponent(fixture.fileName)}`,
  );
});

test("TC-042 page_size=2 walks all six documents once, in list order", { tag: ["@b5", "@P1", "@TC-042"] }, async ({ request }) => {
  const { api } = await createArchive(request);
  await api.addAllSources();

  const titles: string[] = [];
  let token = "";
  for (let page = 0; page < 4; page += 1) {
    const response = await request.get("/api/v1/documents", { params: { page_size: 2, page_token: token } });
    await expectStatus(response, 200);
    const body = (await response.json()) as { items: { title: string }[]; next_page_token: string };
    titles.push(...body.items.map((item) => item.title));
    token = body.next_page_token;
    if (!token) break;
  }

  expect(titles).toEqual(titlesInDefaultOrder);
  expect(token).toBe("");
});

test("TC-043 a page token from another query is 400", { tag: ["@b5", "@P1", "@TC-043"] }, async ({ request }) => {
  const { api } = await createArchive(request);
  await api.addAllSources();
  const first = (await (await request.get("/api/v1/documents", { params: { page_size: 2 } })).json()) as {
    next_page_token: string;
  };

  const response = await request.get("/api/v1/documents", {
    params: { page_size: 2, q: "анализ", page_token: first.next_page_token },
  });

  await expectStatus(response, 400);
  expect(await problemCode(response)).toBe("invalid_page_token");
});

test("TC-090 another archive's document is 404, not 403", { tag: ["@b5", "@P0", "@TC-090"] }, async ({ playwright, baseURL }) => {
  const owner = await playwright.request.newContext({ baseURL });
  const stranger = await playwright.request.newContext({ baseURL });
  const document = await (await createArchive(owner)).api.addSource(blood);
  await createArchive(stranger);

  for (const path of [`/api/v1/documents/${document.id}`, `/api/v1/documents/${document.id}/content`]) {
    const response = await stranger.get(path);
    await expectStatus(response, 404);
    expect(await problemCode(response)).toBe("not_found");
  }
  await owner.dispose();
  await stranger.dispose();
});

test("TC-094 document responses are no-store; the PDF is sandboxed and nosniff", { tag: ["@b5", "@P0", "@TC-094"] }, async ({ request }) => {
  const { api } = await createArchive(request);
  const document = await api.addSource(blood);

  for (const path of ["/api/v1/documents", `/api/v1/documents/${document.id}`]) {
    expect((await request.get(path)).headers()["cache-control"], path).toBe("no-store");
  }
  const pdf = await request.get(`/api/v1/documents/${document.id}/content?disposition=inline`);
  await expectStatus(pdf, 200);
  expect(pdf.headers()["cache-control"]).toBe("no-store");
  expect(pdf.headers()["x-content-type-options"]).toBe("nosniff");
  expect(pdf.headers()["content-security-policy"]).toContain("sandbox");
  expect(pdf.headers()["content-type"]).toBe("application/pdf");
});

test.describe("documents.update preconditions", () => {
  test("TC-058 PATCH without If-Match is 428", { tag: ["@b6", "@P0", "@TC-058"] }, async ({ request }) => {
    const { api } = await createArchive(request);
    const document = await api.addSource(blood);

    const response = await api.send("PATCH", `/api/v1/documents/${document.id}`, { data: { note: "Натощак" } });

    await expectStatus(response, 428);
    expect(await problemCode(response)).toBe("precondition_required");
  });

  test("TC-059 PATCH with a stale ETag is 412 with the current ETag", { tag: ["@b6", "@P0", "@TC-059"] }, async ({ request }) => {
    const { api } = await createArchive(request);
    const document = await api.addSource(blood);
    await expectStatus(
      await api.send("PATCH", `/api/v1/documents/${document.id}`, {
        data: { note: "Первая правка" },
        headers: { "If-Match": document.etag },
      }),
      200,
    );

    const stale = await api.send("PATCH", `/api/v1/documents/${document.id}`, {
      data: { note: "Вторая правка" },
      headers: { "If-Match": document.etag },
    });

    await expectStatus(stale, 412);
    const problem = (await stale.json()) as { code: string; etag?: string };
    expect(problem.code).toBe("version_conflict");
    expect(problem.etag).toBeTruthy();
    expect(problem.etag).not.toBe(document.etag);
  });

  test("TC-097 PATCH with workspace_id or version is 422", { tag: ["@b6", "@P1", "@TC-097"] }, async ({ request }) => {
    const { api, workspaceId } = await createArchive(request);
    const document = await api.addSource(blood);

    for (const extra of [{ workspace_id: workspaceId }, { version: 99 }]) {
      const response = await api.send("PATCH", `/api/v1/documents/${document.id}`, {
        data: { note: "Натощак", ...extra },
        headers: { "If-Match": document.etag },
      });
      await expectStatus(response, 422);
      expect(await problemCode(response)).toBe("validation_error");
    }
  });
});
