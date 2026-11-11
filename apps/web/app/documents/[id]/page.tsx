import { DocumentScreen } from "@/components/documents/DocumentScreen";

export default async function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DocumentScreen id={id} />;
}
