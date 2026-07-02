import js from "@eslint/js";
import tseslint from "typescript-eslint";
import pluginVue from "eslint-plugin-vue";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs["flat/recommended"],
  {
    languageOptions: {
      globals: {
        AbortController: "readonly",
        Blob: "readonly",
        clearTimeout: "readonly",
        document: "readonly",
        DOMParser: "readonly",
        DOMRect: "readonly",
        DragEvent: "readonly",
        Event: "readonly",
        fetch: "readonly",
        File: "readonly",
        HTMLButtonElement: "readonly",
        HTMLDivElement: "readonly",
        HTMLElement: "readonly",
        HTMLImageElement: "readonly",
        HTMLInputElement: "readonly",
        HTMLTextAreaElement: "readonly",
        KeyboardEvent: "readonly",
        localStorage: "readonly",
        MediaQueryListEvent: "readonly",
        MouseEvent: "readonly",
        PointerEvent: "readonly",
        requestAnimationFrame: "readonly",
        ResizeObserver: "readonly",
        setTimeout: "readonly",
        SVGGElement: "readonly",
        SVGGraphicsElement: "readonly",
        SVGSVGElement: "readonly",
        URL: "readonly",
        window: "readonly",
      },
    },
  },
  {
    files: ["**/*.vue"],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
      },
    },
  },
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "vue/multi-word-component-names": "off",
    },
  },
);
