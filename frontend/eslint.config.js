import js from "@eslint/js"
import pluginVue from "eslint-plugin-vue"
import globals from "globals"
import tseslint from "typescript-eslint"

const vueAndTypeScriptFiles = ["**/*.{ts,tsx,vue}"]

export default tseslint.config(
  {
    ignores: ["coverage/**", "dist/**", "node_modules/**"],
  },
  {
    files: vueAndTypeScriptFiles,
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommendedTypeChecked,
      ...pluginVue.configs["flat/recommended"],
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        parser: tseslint.parser,
        projectService: true,
        extraFileExtensions: [".vue"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
  {
    files: ["src/**/domain/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "vue",
              message: "Domain code must remain independent of Vue.",
            },
          ],
          patterns: [
            {
              group: [
                "**/application",
                "**/application/**",
                "**/adapters",
                "**/adapters/**",
                "**/ui",
                "**/ui/**",
                "**/composition",
                "**/composition/**",
                "**/generated",
                "**/generated/**",
                "vue/**",
              ],
              message: "Domain code may not depend on outward frontend layers.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/**/application/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "vue",
              message: "Application code must remain independent of Vue.",
            },
          ],
          patterns: [
            {
              group: [
                "**/adapters",
                "**/adapters/**",
                "**/ui",
                "**/ui/**",
                "**/composition",
                "**/composition/**",
                "**/generated",
                "**/generated/**",
                "**/browser-storage",
                "**/browser-storage/**",
                "**/storage",
                "**/storage/**",
                "vue/**",
              ],
              message: "Application code may not depend on outward or browser-specific layers.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/**/ui/**/*.{ts,tsx,vue}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/adapters", "**/adapters/**"],
              message: "UI code must depend on ports, not concrete adapters.",
            },
          ],
        },
      ],
    },
  },
)
