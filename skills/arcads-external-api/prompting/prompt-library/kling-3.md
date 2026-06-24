# Kling 3.0 Prompting Guide

## API Access

Kling-generated assets are accessed via Arcads' b-roll or scene flows.
- Asset responses return `type: "kling_30"`
- No dedicated Kling route in the OpenAPI — use `CreateBRollDto` or `CreateSceneDto`

## Prompt Template

```
{{SUBJECT}}. {{ACTION_MOTION}}. Environment: {{ENV}}. Camera: {{CAM}}. Mood: {{MOOD}}. Avoid: {{NEGATIVE}}.
```

## Best Practices

- Articulate subject, setting, and motion path with specificity
- Distinguish stylistic choices from content descriptions
- When providing reference or start frames (base64 encoded), clarify how motion should interact with them

## Example

"Artisan pours freshly brewed espresso in slow motion, liquid cascades in thin stream. Environment: warm café counter, morning light through frosted glass. Camera: extreme close-up, rack focus from pour to cup. Mood: calm, premium, ritualistic. Avoid: text overlays, logos, people's faces."

## Known Constraints

- `endFrame` is broken — do not use alone (triggers billed failure) or combined with `startFrame` (returns 500)
- B-roll is silent by nature — redirect any speech requests to Seedance 2.0, Sora 2, or Veo 3.1

## Duration

5 or 10 seconds only.
