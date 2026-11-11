"use client";

import { useState } from "react";

import { newIdempotencyKey } from "@/lib/api/client";
import { useCreateWorkspace, useSession } from "@/lib/api/queries";
import { checkPdfFile } from "@/lib/api/upload";
import { policyVersion } from "@/lib/policy";
import { errorTitles } from "@/lib/texts";

import { AppHeader } from "./AppHeader";
import { ArchiveScreen } from "./ArchiveScreen";
import { BootUnavailable } from "./BootUnavailable";
import { EmptyArchive } from "./EmptyArchive";
import { useProblem } from "./use-problem";

/**
 * `/` (FE-10, FE-11): the session decides between onboarding and the archive. The archive is
 * created only after the consent and the choice of the first file, then its key is shown once.
 */
export function HomeScreen() {
  const session = useSession();
  const createWorkspace = useCreateWorkspace();
  const createProblem = useProblem(createWorkspace.error);
  // One intention «create my archive»: a retry after a lost answer gets the same archive back.
  const [workspaceKey] = useState(newIdempotencyKey);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | undefined>();

  if (session.isPending) return <AppHeader />;
  if (session.isError) {
    return (
      <>
        <AppHeader />
        <BootUnavailable onRetry={() => void session.refetch()} retrying={session.isFetching} />
      </>
    );
  }
  if (session.data) {
    return (
      <ArchiveScreen
        session={session.data}
        initialFiles={pendingFiles}
        onInitialFilesDone={() => setPendingFiles([])}
        issuedKey={issuedKey}
        onKeyShown={() => setIssuedKey(null)}
      />
    );
  }

  async function startArchive(files: File[]) {
    const [first] = files;
    if (!first) return;
    // Checked before the archive exists: a wrong file must not create an empty archive (TC-015).
    const rejected = await checkPdfFile(first);
    setFileError(rejected ? errorTitles[rejected] : undefined);
    if (rejected) return;
    createWorkspace.mutate(
      { idempotencyKey: workspaceKey, policyVersion },
      {
        onSuccess: (created) => {
          setPendingFiles(files);
          setIssuedKey(created.access_key);
        },
      },
    );
  }

  return (
    <>
      <AppHeader />
      <EmptyArchive
        needsConsent
        busy={createWorkspace.isPending}
        error={fileError ?? createProblem?.title}
        onFiles={(files) => void startArchive(files)}
      />
    </>
  );
}
