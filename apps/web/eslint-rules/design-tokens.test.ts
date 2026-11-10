// @vitest-environment node
import { RuleTester } from "eslint";
import { describe, it } from "vitest";

import plugin from "./design-tokens.mjs";

RuleTester.describe = describe;
RuleTester.it = it;

const ruleTester = new RuleTester({
  languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
});

ruleTester.run("no-hex-color", plugin.rules["no-hex-color"], {
  valid: [
    `const a = <div className="bg-surface text-text" />;`,
    `const url = "/api/v1/documents/1/content#view=FitH";`,
    `const style = { color: "var(--c-text)" };`,
  ],
  invalid: [
    { code: `const a = <div style={{ color: "#171717" }} />;`, errors: [{ messageId: "hex" }] },
    { code: "const shadow = `0 0 0 1px #fff`;", errors: [{ messageId: "hex" }] },
    { code: `const c = "#0F766Ecc";`, errors: [{ messageId: "hex" }] },
  ],
});

ruleTester.run("tailwind-tokens", plugin.rules["tailwind-tokens"], {
  valid: [
    `const a = <div className="gap-2 p-4 px-2.5 md:p-6 -mt-1 mx-auto pb-safe" />;`,
    `const a = <div className="data-[state=open]:animate-dialog-in aria-disabled:bg-disabled-bg" />;`,
    `const a = <div className={cn("gap-6", isOpen && "p-8")} />;`,
    `const label = "Поиск [по названию] (PDF)";`,
    "const a = <div className={`p-${size}`} />;",
  ],
  invalid: [
    { code: `const a = <div className="gap-[13px]" />;`, errors: [{ messageId: "arbitrary" }] },
    { code: `const a = <div className="bg-(--c-bg)" />;`, errors: [{ messageId: "arbitrary" }] },
    {
      code: `const a = <div className="md:hover:w-[420px]" />;`,
      errors: [{ messageId: "arbitrary" }],
    },
    {
      code: `const a = <div className="p-7 gap-9" />;`,
      errors: [{ messageId: "spacing" }, { messageId: "spacing" }],
    },
    { code: `const a = <div className={cn("mt-px")} />;`, errors: [{ messageId: "spacing" }] },
    { code: `const sizeClasses = { md: "px-3.5" };`, errors: [{ messageId: "spacing" }] },
    {
      code: "const a = <div className={`flex ${x} gap-[3px]`} />;",
      errors: [{ messageId: "arbitrary" }],
    },
  ],
});
