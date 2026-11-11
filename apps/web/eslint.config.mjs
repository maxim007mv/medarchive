import { FlatCompat } from "@eslint/eslintrc";

import designTokens from "./eslint-rules/design-tokens.mjs";

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

const eslintConfig = [
  { ignores: [".next/**", "next-env.d.ts", "lib/api/schema.d.ts", "coverage/**"] },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    files: ["**/*.{ts,tsx}"],
    // The rule's own tests are made of forbidden values.
    ignores: ["eslint-rules/**"],
    plugins: { "design-tokens": designTokens },
    rules: {
      "design-tokens/no-hex-color": "error",
      "design-tokens/tailwind-tokens": "error",
    },
  },
];

export default eslintConfig;
