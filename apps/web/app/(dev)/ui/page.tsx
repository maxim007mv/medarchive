import { notFound } from "next/navigation";

import { Gallery } from "./gallery";

// Visual snapshots of components/ui; not part of the product.
export default function UiGalleryPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <Gallery />;
}
