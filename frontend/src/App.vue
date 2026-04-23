<template>
  <div class="rag-app">
    <RouterView />
  </div>
</template>

<script setup>
</script>

<style>
/* 全局样式 - 复用 testplat 的深色主题 */
:root {
  --bg-primary: #0c0e14;
  --bg-panel: #12151e;
  --bg-raised: #1a1d28;
  --bg-hover: #1f2330;
  --bg-input: #161922;

  --border: #252a3a;
  --border-subtle: #1e2233;

  --text-primary: #e4e7f0;
  --text-secondary: #8891a8;
  --text-muted: #555f7a;

  --accent: #3d9aff;
  --accent-dim: rgba(61, 154, 255, 0.12);
  --accent-rgb: 61, 154, 255;

  --success: #34d399;
  --warning: #fbbf24;
  --danger: #f87171;

  --radius: 8px;
  --radius-sm: 6px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.rag-app {
  min-height: 100vh;
  background: var(--bg-primary);
}

/* Element Plus 覆盖 */
.el-button--primary {
  --el-button-bg-color: var(--accent);
  --el-button-border-color: var(--accent);
  --el-button-hover-bg-color: #5aa8ff;
  --el-button-hover-border-color: #5aa8ff;
}

.el-input__wrapper {
  background: var(--bg-input) !important;
  border: 1px solid var(--border) !important;
  box-shadow: none !important;
}

.el-input__inner {
  color: var(--text-primary) !important;
}

.el-input__inner::placeholder {
  color: var(--text-muted) !important;
}

.el-upload-dragger {
  background: var(--bg-panel) !important;
  border: 1px dashed var(--border) !important;
}

.el-message {
  --el-message-bg-color: var(--bg-panel);
  border: 1px solid var(--border);
}
</style>
