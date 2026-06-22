# Jobs-Skills MVP Workflow Diagram

This diagram captures the current resume/role-first workflow, including where parser agents, the deterministic scoring engine, and explainer agents sit in the product flow.

```mermaid
flowchart TD
    U["User in Telegram"] --> START["/start"]
    START --> GUIDE["First-time guide<br/>Explains recommender, privacy, and outputs"]
    START --> RESUME["Upload resume<br/>PDF/DOCX"]
    START --> ROLESTART["Search starting role<br/>Dataset role baseline"]

    RESUME --> ACK["Resume received<br/>Parsing skills now"]
    ACK --> DOCINGEST["Document ingestion<br/>Extract runtime text only"]
    DOCINGEST --> RULEPARSER
    DOCINGEST --> AGENTPARSER

    subgraph PARSER["Parser Layer"]
        RULEPARSER["Rule-based skill extractor<br/>Fallback path"]
        AGENTPARSER["Parser agent, if configured<br/>Extracts evidence, inferred level, confidence, reason"]
        MAPSKILLS["Map to SkillsFuture skills<br/>Exact, alias, fuzzy, or agent-suggested mapping"]
        CLEANEVIDENCE["Evidence filtering<br/>Avoid contact details and weak resume headers"]
        RULEPARSER --> MAPSKILLS
        AGENTPARSER --> MAPSKILLS
        MAPSKILLS --> CLEANEVIDENCE
    end

    ROLESTART --> ROLEPROFILE["Build draft skill profile<br/>From dataset role requirements"]
    CLEANEVIDENCE --> DRAFT["Draft skill profile<br/>Skill, level, user-facing reason"]
    ROLEPROFILE --> DRAFT

    DRAFT --> REVIEW["Review all skills<br/>Edit level, remove skill, add skill"]
    REVIEW --> CONFIRM["Confirmed user skill vector<br/>user_vector[skill_id] = level"]

    CONFIRM --> TARGETMENU["Choose target mode"]
    TARGETMENU --> EXPLORE["Explore pathways<br/>Find similar roles"]
    TARGETMENU --> ADVANCE["Advance roles<br/>Find higher-level adjacent roles"]
    TARGETMENU --> TARGETROLE["Search target role<br/>Dataset role comparison"]
    TARGETMENU --> JD["Paste/upload JD<br/>Direct suitability scoring"]

    JD --> JDRULE
    JD --> JDAGENT
    subgraph JDPARSER["JD Parser Layer"]
        JDRULE["Rule-based JD parser"]
        JDAGENT["Parser agent, if configured<br/>Maps JD requirements to SkillsFuture skills"]
        JDREQ["Target skill requirements<br/>role_vector[skill_id] = target level"]
        JDRULE --> JDREQ
        JDAGENT --> JDREQ
    end

    EXPLORE --> ROLEVECTORS["Dataset role vectors"]
    ADVANCE --> ROLEVECTORS
    TARGETROLE --> ROLEVECTORS
    ROLEVECTORS --> EXACT
    JDREQ --> EXACT
    CONFIRM --> EXACT

    subgraph SCORING["Deterministic Scoring Engine"]
        EXACT["Exact skill-id matching<br/>Missing user skill = level 0"]
        SCORE["Suitability %<br/>sum(min(user,target)) / sum(target)"]
        GAP["Gap table<br/>gap = max(target - user, 0)"]
        RANK["Role ranking<br/>fit, gap cost, policy filters"]
        EXACT --> SCORE
        SCORE --> GAP
        GAP --> RANK
    end

    RANK --> RELATED["Related-skill explanation layer<br/>Semantic/curated matches only; does not change score"]
    RELATED --> RESULTS["Compact result<br/>Suitability, matched skills, top gaps"]

    RESULTS --> RULEEXPLAIN
    RESULTS --> AGENTEXPLAIN
    subgraph EXPLAIN["Explainability Layer"]
        RULEEXPLAIN["Rule-based explanation fallback"]
        AGENTEXPLAIN["Explainer agent, if configured<br/>Summarises why score/gaps make sense"]
        ACTIONS["Action plan generator<br/>Uses proficiency descriptions and K&A items"]
        REPORTS["Normal/debug reports<br/>Normal hides internals; debug keeps audit trail"]
        RULEEXPLAIN --> ACTIONS
        AGENTEXPLAIN --> ACTIONS
        ACTIONS --> REPORTS
    end

    REPORTS --> USERACTIONS["User actions<br/>Why this score, show gaps, generate action plan, generate report"]
    USERACTIONS --> U

    DATASETS["SkillsFuture datasets<br/>Role-skill requirements, unique skills, K&A rows"] --> MAPSKILLS
    DATASETS --> ROLEPROFILE
    DATASETS --> ROLEVECTORS
    DATASETS --> ACTIONS
```

## Key Annotations

- Parser agents are advisory. They extract skills, evidence, inferred levels, and reasons, but they do not calculate final suitability.
- The scoring engine is deterministic. MVP scoring uses exact `skill_id` matching and all skill weights stay at `1.0`.
- The related-skill layer is explanation-only. It can say a confirmed skill is similar to a target gap, but it does not change the suitability percentage.
- Explainer agents are advisory. They summarise parser/scoring outputs for users, while rule-based explanations remain the fallback.
- Raw resume and JD text should be read at runtime only. Normal Telegram reports/action plans are transient attachments; debug/local artifacts may persist reviewed skills, evidence summaries, scores, gaps, and source notes for audit.
