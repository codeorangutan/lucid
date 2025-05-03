# LUCID Project Flow Diagram

flowchart TD
    subgraph Intake
        A[Receive Referral Email]:::done
        B[Parse Email & Save to DB]:::done
        C[Send Acknowledgement]:::pending
    end

    subgraph Test
        D[Request CNS Test via Playwright]:::done
        E[Monitor for Report Notification]:::part
    end

    subgraph Processing
        F[Download & Parse Report]:::part
        G[Reformat Report]:::pending
        H[Save Reformatted Report to DB]:::pending
    end

    subgraph Output
        I[Send Report to Referrer]:::pending
        J[Log & Audit]:::part
    end

    O[Orchestrator / Main Controller]:::planned

    A --> B --> C
    C --> O
    O --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J

    classDef done fill:#d4ffd4,stroke:#228B22,stroke-width:2px;
    classDef part fill:#fffdd4,stroke:#bbaa00,stroke-dasharray: 5 5;
    classDef pending fill:#ffd4d4,stroke:#b22222,stroke-dasharray: 2 2;
    classDef planned fill:#d4e2ff,stroke:#1e90ff,stroke-width:3px;
```

---

**Legend:**
- <span style="background-color:#d4ffd4;">Green</span> = Implemented
- <span style="background-color:#fffdd4;">Yellow</span> = Partially Implemented
- <span style="background-color:#ffd4d4;">Red</span> = Not Implemented
- <span style="background-color:#d4e2ff;">Blue</span> = Orchestrator (Planned)

_Update the diagram and legend as progress is made._
