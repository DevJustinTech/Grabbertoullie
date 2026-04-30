## 2025-03-01 - Disabled Button Contrast Trap with Tailwind

**Learning:** When styling disabled buttons in Tailwind, using `disabled:bg-zinc-300` combined with `text-white` creates a critical accessibility failure (WCAG contrast ratio of ~1.44), making the text nearly invisible to many users. The visual indicator of being disabled shouldn't compromise the readability of the button text itself.

**Action:** Instead of dramatically shifting the background color to a very light gray while keeping white text, keep the original darker background color (`disabled:bg-zinc-900`) and use `disabled:opacity-50` along with `disabled:cursor-not-allowed`. This ensures the contrast ratio between text and background remains exactly the same while clearly indicating the inactive state.