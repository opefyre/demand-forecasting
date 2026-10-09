# Global motion — 9 October 2026

## Ownership

- `frontend/src/tokens.css`: all duration, easing, distance, scale and scroll tokens.
- `frontend/src/ui-framework.css`: all authored transition/animation rules and keyframes.
- `frontend/src/ui-motion.jsx`: shared visual-state changes and Radix notification presence.
- `frontend/src/motion.mjs`: browser support, cancellation and reduced-motion policy.

No inline styles, new animation service or forecasting changes. Radix Presence is
an existing open-source dependency, now registered directly instead of rebuilding
its exit-animation lifecycle.

## Behaviour

Controls share 120–160 ms hover, press, colour, disabled and focus-shadow transitions.
Content/menu/dialog entry uses 220 ms; exit uses 140 ms; layout changes use 280 ms.
Sidebars, navigation, Settings sections, forecast/import/order steps, factor details,
forecast views, result pagination and new-chat activation use the shared system.
Messages, loading states, errors and notices enter consistently. Dialogs, tools,
pickers, tooltips and notifications have exit animations. Disclosures expand and
collapse smoothly where the browser supports intrinsic-size interpolation.

Native view transitions preserve the composer's movement between welcome and
conversation. Other browsers receive a CSS reveal without blocking the operation.
Navigation remains clickable during transitions. Updates execute once; quick
navigation skips superseded animation. Inputs are never remounted to animate.
Typing, validation, polling and calculations remain immediate. Charts are not
redrawn from artificial zero values or altered to imply changes in demand.
The character keeps its independent clocks and offscreen pausing.

Reduced-motion preference disables all authored animations, transitions and smooth
scrolling, and bypasses native view transitions. No persistent `will-change` layers
or global `transition: all` rules.

## Verification

201 frontend tests and production build pass; CSS ownership/token checks; simulated
unsupported, hidden, reduced-motion, cancelled and overlapping transitions.
Browser checks cover English synthetic chat, Persian Settings, menu entry/exit,
notification entry/removal, mobile dialog geometry and keyboard focus restoration.
The native-transition fixture reports support; one synthetic request produces two
messages, leaves the composer docked and restores input focus without runtime warnings.
No OpenAI calls, live-source refreshes or changes to client data.

This is a motion-system delivery, not a claim that all legacy screen layouts have
been rebuilt. Screenshot: `docs/screenshots/global-motion-home.png`.
