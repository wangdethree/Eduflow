import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'

export default defineConfigWithVueTs(
  {
    name: 'eduflow/files',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },
  {
    name: 'eduflow/ignores',
    ignores: ['dist/**', 'node_modules/**', '*.tsbuildinfo'],
  },
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  skipFormatting,
  {
    rules: {
      // API 异常对象由 Axios 在运行时提供，界面层保留灵活类型。
      '@typescript-eslint/no-explicit-any': 'off',
      'vue/multi-word-component-names': 'off',
    },
  },
)
