# Minimal Workflow Diagram

This is the simplest version for slides, quick judging walkthroughs, or first-time product explanations.

```mermaid
flowchart TD
    A["<div style='text-align:center'><b>Start</b></div>"] --> B["<div style='text-align:center'><b>Choose starting point</b></div><div style='text-align:left'>• Upload resume<br/>• Choose current role from dataset role list</div>"]

    B --> P["<div style='text-align:center'><b>Parser layer (resume path)</b></div>"]
    B --> C["<div style='text-align:center'><b>Review skills parsed or chosen</b></div>"]
    P --> C

    C --> D["<div style='text-align:center'><b>Choose goal</b></div><div style='text-align:left'>• Explore career pathways<br/>• Advance in similar role track<br/>• Compare with target role<br/>• Compare with job description</div>"]

    D --> S["<div style='text-align:center'><b>Scoring engine</b></div>"]
    D --> X["<div style='text-align:center'><b>Explainer layer</b></div>"]
    S --> E["<div style='text-align:center'><b>Get recommendation</b></div><div style='text-align:left'>• Suitability score<br/>• Skill gaps<br/>• Action plan</div>"]
    X --> E
```

## Minimal Flow

1. Start.
2. User uploads a resume or chooses their current role.
3. Resume parsing or role selection creates a draft skill profile.
4. User reviews the skills and can edit, remove, or add skills.
5. User chooses a goal.
6. Scoring and explanation layers produce recommendations, skill gaps, and an action plan.
