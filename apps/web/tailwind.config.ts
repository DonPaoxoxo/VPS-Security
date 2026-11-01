import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        "card-border": "hsl(var(--card-border))",
        muted: "hsl(var(--muted))",
        "muted-foreground": "hsl(var(--muted-foreground))",
        accent: "hsl(var(--accent))",
        healthy: "hsl(var(--healthy))",
        warning: "hsl(var(--warning))",
        critical: "hsl(var(--critical))",
        info: "hsl(var(--info))",
      },
      borderRadius: {
        lg: "0.5rem",
        md: "0.375rem",
      },
    },
  },
  plugins: [],
};

export default config;
