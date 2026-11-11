import { execFileSync } from "node:child_process";

import { expect, test } from "@playwright/test";

import { createArchive, expectStatus } from "../../support/archive";
import { sources } from "../../support/manifest";

// TC-096b, threat T6: someone with write access to the database swaps the title ciphertexts of
// two documents. AAD = document_id, so decryption fails: 500 `internal` without any title.
// Needs the compose stack on this machine: E2E_COMPOSE_PROJECT names it (default `medarchive`).
const DB_CONTAINER = `${process.env.E2E_COMPOSE_PROJECT ?? "medarchive"}-db-1`;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function swapTitleCiphertexts(workspaceId: string, first: string, second: string): void {
  for (const id of [workspaceId, first, second]) if (!UUID.test(id)) throw new Error(`not a uuid: ${id}`);
  const sql = `BEGIN;
    SELECT set_config('app.workspace_id', '${workspaceId}', true);
    UPDATE app.documents d SET title_ct = o.title_ct
      FROM app.documents o
      WHERE (d.id, o.id) IN (('${first}', '${second}'), ('${second}', '${first}'));
    COMMIT;`;
  execFileSync("docker", ["exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "medarchive", "-v", "ON_ERROR_STOP=1", "-qc", sql]);
}

test("TC-096b swapped title ciphertexts do not decrypt and leak no title", { tag: ["@b7", "@P0", "@TC-096b"] }, async ({ request }) => {
  const { api, workspaceId } = await createArchive(request);
  const [first, second] = [await api.addSource(sources[0]), await api.addSource(sources[1])];

  swapTitleCiphertexts(workspaceId, first.id, second.id);

  for (const document of [first, second]) {
    const response = await request.get(`/api/v1/documents/${document.id}`);
    await expectStatus(response, 500);
    const body = await response.text();
    expect(JSON.parse(body).code).toBe("internal");
    for (const source of [sources[0], sources[1]]) expect(body).not.toContain(source.title);
  }
});
