## 2025-03-01 - Disabled Button Contrast Trap with Tailwind

**Learning:** When styling disabled buttons in Tailwind, using `disabled:bg-zinc-300` combined with `text-white` creates a critical accessibility failure (WCAG contrast ratio of ~1.44), making the text nearly invisible to many users. The visual indicator of being disabled shouldn't compromise the readability of the button text itself.

**Action:** Instead of dramatically shifting the background color to a very light gray while keeping white text, keep the original darker background color (`disabled:bg-zinc-900`) and use `disabled:opacity-50` along with `disabled:cursor-not-allowed`. This ensures the contrast ratio between text and background remains exactly the same while clearly indicating the inactive state.
## 2025-03-02 - Interactive Empty States Reduce Friction

**Learning:** Static examples in empty states (like "Try searching for...") ask users to do unnecessary work (typing the example). Users often want a quick, zero-friction way to see how the app works on their first visit.

**Action:** Whenever possible, convert static example queries or actions in empty states into interactive, one-click buttons that automatically populate and submit the form. This provides immediate value and reduces the barrier to first interaction.
