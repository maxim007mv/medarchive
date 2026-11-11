import type { Metadata } from "next";

import { SettingsScreen } from "@/components/documents/SettingsScreen";
import { texts } from "@/lib/texts";

export const metadata: Metadata = { title: `${texts["settings.title"]} · ${texts["app.name"]}` };

export default function SettingsPage() {
  return <SettingsScreen />;
}
