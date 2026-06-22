# Simplified User Workflow Diagram

This version explains the recommender flow for non-technical users, judges, and demo viewers.

```mermaid
flowchart TD
    A["Start in Telegram"] --> B["Choose how to begin"]

    B --> C["Upload resume"]
    B --> D["Search for a current or starting role"]

    C --> E["System reads the resume<br/>and suggests possible skills"]
    D --> F["System uses the selected role<br/>to create a starting skill profile"]

    E --> G["Review skill profile"]
    F --> G

    G --> H["User checks each skill"]
    H --> H1["Edit skill level"]
    H --> H2["Remove wrong skill"]
    H --> H3["Add missing skill"]
    H1 --> I["Confirm skills"]
    H2 --> I
    H3 --> I
    G --> I

    I --> J["Choose goal"]

    J --> K["Explore similar career pathways"]
    J --> L["Find next-step roles"]
    J --> M["Compare with a specific role"]
    J --> N["Paste a job description"]

    K --> O["System compares your skills<br/>with role requirements"]
    L --> O
    M --> O
    N --> O

    O --> P["See suitability score"]
    P --> Q["Understand why"]
    P --> R["View skill gaps"]
    P --> S["Generate action plan"]

    Q --> T["Clear explanation of matched skills<br/>and skills pulling the score down"]
    R --> U["Current level vs target level"]
    S --> V["Practical learning actions<br/>based on SkillsFuture requirements"]

    T --> W["User decides next step"]
    U --> W
    V --> W
```

## Plain-Language Summary

1. The user starts by uploading a resume or choosing a role.
2. The system suggests a skill profile.
3. The user reviews and corrects the skill profile before any scoring happens.
4. The user chooses a career goal, such as exploring pathways or comparing against a job description.
5. The system compares the confirmed skills against role or job requirements.
6. The user receives a suitability score, skill gaps, and a practical action plan.

## What The System Explains

- Why a role or pathway was recommended.
- Which skills matched the target.
- Which skills are missing or below the target level.
- Why similar skills may still count as gaps when SkillsFuture defines them separately.
- What actions the user can take next to close the gaps.

## Important User Promise

The user is not scored directly from hidden assumptions. They can review, edit, remove, and add skills before the system calculates suitability.
