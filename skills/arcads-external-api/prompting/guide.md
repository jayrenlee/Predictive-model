# Creative Brief Playbook

Structured workflow for developing video ad briefs before using model-specific prompting tools.

## 1. Capture Marketing Intent

Gather core information:
- Target audience
- Desired viewer response
- Product details with benefits
- Opening hook strategy
- Call-to-action language
- Project constraints (duration, format restrictions)

## 2. Develop a Unified Prompt

Consolidate the brief into one paragraph of clear direction. Specify:
- Subject matter
- Location
- Camera techniques
- Lighting approach
- Visual style
- Audio characteristics (when the chosen API supports it)

## 3. Select the Right API Route

Match your project to the appropriate vendor using decision trees in `../SKILL.md` and `../reference.md`, then open the corresponding template file for Sora 2, Veo 3.1, Kling 3.0, or Nano Banana to align language with that platform's requirements.

## 4. Integrate Brand Guidelines

Reference `MASTER_CONTEXT.md` for:
- Established brand voice
- Prohibited language
- Previously successful prompts (these take priority over generic suggestions)

## 5. Final Validation Checklist

Before submission, confirm:
- [ ] All required JSON fields are present
- [ ] Prompt follows vendor-specific guidance
- [ ] No sensitive information is exposed
- [ ] User has approved aspect ratio and timing specifications
