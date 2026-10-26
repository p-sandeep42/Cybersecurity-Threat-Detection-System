# Browser and accessibility verification

Verified in installed Chrome using Playwright, synthetic accounts, temporary databases and ephemeral local servers. No live owner data or credentials appear in the screenshots.

## Automated checks performed

- No browser summary before opt-in; an opted-in submission contains only the documented aggregate fields.
- Opt-out clears collection, same-tab consent survives navigation, and cached pages honor a subsequent opt-out.
- Keyboard-only and touch login both work and produce the appropriate summary types.
- Hidden pointer events are ignored and visibility-interrupted intervals are labeled.
- Overview polling preserves unsubmitted filters, can be paused, skips hidden pages and stops on session expiry.
- No JavaScript errors in the main flow.
- Desktop and 390-pixel mobile layouts have no page-level horizontal overflow.
- Axe-core checks for WCAG 2 A/AA and 2.1 AA report zero violations on the tested owner login, demo login, overview, alert list and investigation pages, including mobile overview and touch demo login.

Raw records: [main checks](browser-checks.json), [edge cases](browser-edge-checks.json).

## Visual review

The generated desktop and mobile screenshots were inspected for readable controls, clear consent states, usable spacing, visible labels and contained tables. The mobile overview stacks its cards in one column; the long page scrolls vertically without clipping its metrics or consent information.

- [Demo consent, desktop](screenshots/demo-consent-desktop.png)
- [Demo, mobile](screenshots/demo-mobile.png)
- [Overview, desktop](screenshots/overview-desktop.png)
- [Overview, mobile](screenshots/overview-mobile.png)
- [Investigation, desktop](screenshots/investigation-desktop.png)

Automated checks and a keyboard/visual review do not constitute full accessibility certification. Screen-reader testing, additional browser engines and a wider device matrix remain future verification work.
