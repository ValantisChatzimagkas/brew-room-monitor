import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import betterTailwind from "eslint-plugin-better-tailwindcss";

// Design system: shadcn components in src/components/ui are the only UI kit.
// These bans also apply inside ui/, so a third-party registry item that pulls in
// its own animation or UI library fails lint.
const foreignUi = {
  group: [
    "@mui/*",
    "@chakra-ui/*",
    "@headlessui/*",
    "antd",
    "react-icons",
    "react-icons/*",
    "@heroicons/*",
    "framer-motion",
    "motion",
    "motion/*",
    "@tsparticles/*",
    "clsx",
    "tailwind-merge",
    "classnames",
  ],
  message: "Not part of the design system: use src/components/ui (shadcn) and cn.",
};
const primitives = {
  group: ["@base-ui/*", "radix-ui", "@radix-ui/*"],
  message: "Primitives are wrapped in src/components/ui: import the wrapper.",
};

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { "better-tailwindcss": betterTailwind },
    settings: { "better-tailwindcss": { entryPoint: "src/app/globals.css" } },
    rules: {
      "better-tailwindcss/no-unknown-classes": "error",
      "better-tailwindcss/no-conflicting-classes": "error",
      "better-tailwindcss/no-restricted-classes": [
        "error",
        { restrict: [{ pattern: "\\[([^\\[\\]]*?)\\](?!:)", message: "Arbitrary value: use a theme token." }] },
      ],
      "react/forbid-elements": [
        "error",
        {
          forbid: ["button", "input", "select", "textarea"].map((element) => ({
            element,
            message: "Use the component from src/components/ui (pnpm exec shadcn add <name>).",
          })),
        },
      ],
      "no-restricted-imports": ["error", { patterns: [foreignUi, primitives] }],
    },
  },
  {
    // Vendored shadcn code wraps primitives and native elements and uses arbitrary values.
    files: ["src/components/ui/**"],
    rules: {
      "better-tailwindcss/no-restricted-classes": "off",
      "react/forbid-elements": "off",
      "no-restricted-imports": ["error", { patterns: [foreignUi] }],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
