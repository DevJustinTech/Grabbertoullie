## 2025-03-01 - Disabled Button Contrast Trap with Tailwind

**Learning:** When styling disabled buttons in Tailwind, using `disabled:bg-zinc-300` combined with `text-white` creates a critical accessibility failure (WCAG contrast ratio of ~1.44), making the text nearly invisible to many users. The visual indicator of being disabled shouldn't compromise the readability of the button text itself.

**Action:** Instead of dramatically shifting the background color to a very light gray while keeping white text, keep the original darker background color (`disabled:bg-zinc-900`) and use `disabled:opacity-50` along with `disabled:cursor-not-allowed`. This ensures the contrast ratio between text and background remains exactly the same while clearly indicating the inactive state.

## 2025-03-03 - Empty State Interactions

**Learning:** Static examples in empty states (like "e.g. search for X") are missed opportunities. Making them interactive one-click trials significantly lowers the barrier to first interaction while also teaching users exactly what formatting the app expects. Additionally, ensuring these interactive elements are fully accessible (proper focus visible states, hover effects, aria-labels) ensures all users benefit from the trial action.

**Action:** Whenever introducing a static text example to guide user input, convert it to an accessible interactive button that automatically runs the example. Add `focus-visible` styling (`focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2`) to align with design system standards.
## 2025-03-02 - Interactive Empty States Reduce Friction

**Learning:** Static examples in empty states (like "Try searching for...") ask users to do unnecessary work (typing the example). Users often want a quick, zero-friction way to see how the app works on their first visit.

**Action:** Whenever possible, convert static example queries or actions in empty states into interactive, one-click buttons that automatically populate and submit the form. This provides immediate value and reduces the barrier to first interaction.
## 2025-03-04 - Keyboard Shortcuts Discovery & Accessibility

**Learning:** When adding global keyboard shortcuts (like `/` to search/focus) to a React application, it is important to prevent default behaviors but more critically, avoid intercepting the keystroke when a user is already typing in an input or textarea element. This ensures the shortcut does not break regular text entry. Additionally, visual hints using styled `<kbd>` tags provide a great way to introduce "power-user" features organically without overwhelming the layout.

**Action:** Whenever implementing a global keyboard shortcut (e.g., using a window event listener inside a `useEffect`), always include a check against `document.activeElement?.tagName` to bypass the shortcut logic if the focus is on an interactive input field (`"INPUT"` or `"TEXTAREA"`).
## 2024-06-01 - Add Clear Button to Chat Input
**Learning:** Implementing a conditional clear ('X') button on the search input significantly enhances usability, allowing users to discard long queries immediately instead of repeatedly tapping backspace. Ensuring the button maintains accessible ARIA labels, hover states, and restores focus to the input prevents disruptions to the keyboard navigation flow.
**Action:** For all future primary search or chat inputs in the app, always consider providing a clear action button with setInput('') and ref.current?.focus() when the input is non-empty.
## 2024-06-02 - Chat Message and Input Accessibility
**Learning:** Screen readers announce visual messaging blocks identically if there is no hidden semantic distinction. Adding visually hidden `sr-only` text ("You said:"/"Bot said:") allows non-visual differentiation of chat sources without altering the UI. Also, using `aria-describedby` links visual shortcut hints explicitly to the input field so they are discovered on focus, which improves discoverability of shortcuts for screen reader users.
**Action:** Always include semantic context text via `sr-only` elements when message roles are only implied by layout/color. Link secondary instruction or shortcut hint text directly to the interactive element it references using `aria-describedby`.
## 2025-03-05 - Contextual Accessibility for Repeated Actions

**Learning:** In UI lists or chat streams where each result generates identical action buttons (e.g., 'Download File'), relying solely on the visible button text creates an accessibility failure. A screen reader user navigating by interactive elements will just hear "Download File" repeated with no context of *which* file they are downloading.

**Action:** Whenever implementing lists or repeating elements with identical action buttons, always inject contextual payload data into a dynamic `aria-label` (e.g., `aria-label={`Download ${bookName}`}`) to ensure screen reader users can distinguish between them.
## 2026-07-04 - Semantic Actionable Lists
**Learning:** When rendering lists of actionable items in the UI (e.g., disambiguation candidate buttons), relying on divs creates an accessibility barrier for screen readers trying to determine the number of options.
**Action:** Structure these elements within semantic `<ul>` and `<li>` tags to improve screen reader accessibility, and ensure the interactive children stretch to fill the item (e.g., using `w-full`) to maintain layout and hit areas.
## 2026-07-04 - Live Chat Announcement
**Learning:** Live chat interfaces do not automatically announce new messages to screen reader users, causing them to miss responses.
**Action:** Always apply `role="log"` and `aria-live="polite"` to the messages container to ensure screen readers naturally announce incoming messages.
