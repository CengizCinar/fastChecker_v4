# Gemini Agent Instructions for FastChecker Project

This project contains two distinct user interfaces (UIs) for the Chrome extension:

1.  **Side Panel UI**: Accessed via the browser's side panel (or popup).
2.  **Browser UI**: Refers to any UI elements injected directly into Amazon web pages (via content scripts).

**CRITICAL GUIDELINES:**

*   **Strict UI Separation**: When a user requests changes related to the **Side Panel UI**, you **MUST NOT** modify any files or logic pertaining to the **Browser UI** (e.g., `content.js`, or any scripts/styles injected into web pages).
*   **Strict UI Separation**: Conversely, if a user requests changes related to the **Browser UI**, you **MUST NOT** modify any files or logic pertaining to the **Side Panel UI** (`sidepanel.html`, `sidepanel.css`, `sidepanel.js`, and any files within the `sidepanel/` directory).




