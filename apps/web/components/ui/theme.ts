export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "theme";

// Runs inline in <head> before first paint (FE-01): the saved choice, else the system preference.
// If storage is blocked the attribute stays unset and tokens.css follows prefers-color-scheme.
export const themeScript = `(function(){try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t!=="light"&&t!=="dark"){t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.dataset.theme=t}catch(e){}})()`;

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Storage blocked: the choice lasts until reload, which is all we can offer.
  }
}
