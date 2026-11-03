// Mid-tone colors that stay readable on both the light and the dark theme.
export const LANGUAGE_COLORS = {
  python: "#3b82f6", javascript: "#eab308", typescript: "#2563eb", java: "#f97316",
  go: "#06b6d4", rust: "#c2410c", ruby: "#e11d48", c: "#64748b", cpp: "#8b5cf6",
};

export const DOMAIN_COLORS = {
  frontend: "#0ea5e9", backend: "#8b5cf6", data: "#10b981", utils: "#f59e0b", general: "#94a3b8",
};

export const LEGENDS = { language: LANGUAGE_COLORS, domain: DOMAIN_COLORS };

export function colorOf(node, colorBy) {
  const table = LEGENDS[colorBy];
  return table[colorBy === "domain" ? node.domain : node.language] || "#94a3b8";
}