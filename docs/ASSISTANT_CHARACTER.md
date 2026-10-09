# Assistant cartoon companion — 8 October 2026

## Active animated version

The shared chat now renders `../frontend/src/assistant-mascot.jsx`, a lightweight
native SVG reconstruction of the approved simple character. The generated image
below remains the design reference, not the active avatar.

Continuous cubic-path interpolation opens curved eyes into circles and closes
them again, with a short blink. Independent eased movements provide small glances,
hand waves and gentle breathing, separated by calm holds. Subtle gradients add
rounded depth without fur or realistic detail. No white background circle.

All colour, timing, easing and transform settings live in `tokens.css`; animation
rules live in the shared `ui-framework.css`. No inline CSS, new dependencies, image
frame swapping, provider calls or JavaScript animation loops. Hidden/offscreen
characters pause; reduced-motion preference disables all movement.

Verification: 182 frontend tests and production build pass. Browser check confirmed
interpolated halfway eye coordinates, not either endpoint; hand rotation also showed
an intermediate angle. Evidence: `screenshots/chat-mascot-mid-morph-synthetic.png`.
The motion-position control is development-only and not shipped in the app.

## Independent motion refinement — 8 October 2026

One shared speed token is now `1.2`: cycle durations are divided by 1.2 for a
20% speed increase. Breathing, eye shape, blinking, glances, each hand, the head
curl and the smile have eight different clocks and staggered starting positions.
Three stable per-instance phase variations keep neighbouring avatars from moving
in lockstep. This is an organic-looking combination of smooth cycles, not true
random scheduling. Calm holds remain; there are no abrupt state changes.

The curl morph changes only its own control points within the continuous body
outline, so no detached tuft or seams appear. Mouth curves morph independently.
Existing hidden/offscreen pausing and reduced-motion behaviour are unchanged.
All settings remain in global tokens/framework styles; no animation library,
inline styles, timers or additional dependencies.

191 frontend tests and production build pass. The running browser reports eight
distinct cycle lengths; breathing resolves to 5 seconds rather than 6. Intermediate
smile paths and independently rotated hands were verified. No AI calls.
Evidence: `screenshots/character-independent-motion.png`.

## Generated design reference

Generated with the built-in image-generation tool. Reference asset:
`../frontend/public/avatars/assistant-mascot-simple.png`.

Concept: an original flat lime-green cartoon companion with a floppy tuft, two
curved eyes, a small smile and a welcoming wave. No fur or realistic rendering.
Inspired by the approachable cartoon
category of Dots and Muse, not a copy of their character designs. The rejected
human portrait is not used by the app.

Used by the shared chat message component for saved, new and pending assistant
messages. User identity unchanged. Global avatar size is 44px. Appearance is controlled by global framework
styles and shared tokens; no inline styles.

Visual references inspected:
- [OpenAI Dots](https://openai.com/index/introducing-dots/)
- [Meta Muse](https://www.punto-informatico.it/meta-muse-video-chat-computer-use-smart-glass/)

## Final generation prompt

Use case: style-transfer. Image 1 is the existing assistant character to simplify. Keep its recognizable lime-green rounded body, single floppy curved tuft, stubby limbs and small waving pose. Redraw it as an extremely simple flat 2D cartoon mascot for a 44px chat avatar. ONE solid vivid lime-green #5ee800 silhouette, with only THREE charcoal face strokes: two small gently curved closed smiling eyes and one small curved smile. Remove the white eye areas, pupils, highlights and eyebrow entirely. No fur, fibers, texture, shading, gradients, lighting, gloss, outlines, 3D depth or cast shadow. Smooth clean vector-like edges and broad simple shapes; happy, calm, minimalist. Preserve the character identity and pose but reduce all visual detail. Center the complete character in a square with generous safe padding for circular cropping. Genuinely transparent background. No text, objects, badges, backdrop disk or additional characters.
