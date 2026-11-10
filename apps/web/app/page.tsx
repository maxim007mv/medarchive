import { Suspense } from "react";

import { HomeScreen } from "@/components/documents/HomeScreen";

// Filters live in the URL (nuqs), which needs a Suspense boundary for prerendering.
export default function HomePage() {
  return (
    <Suspense>
      <HomeScreen />
    </Suspense>
  );
}
