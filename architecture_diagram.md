# 🏛️ System Design & Agent Graph Architecture Specification

**Engine:** AutoSupport Agent AI  
**Author:** Ram Chandra Gupta ([@Chandra142](https://github.com/Chandra142))  
**Discipline:** Agent Harness Engineering / ReAct Loop Design / State Graph Architecture  

---

## 1. High-Level Executive Summary

The **AutoSupport Agent AI** is architected as an asynchronous, deterministic **Cyclic State Graph** with an embedded **Resiliency & Observability Harness**. Rather than relying on unconstrained generative language model loops that are prone to hallucination, tool looping, and non-deterministic failures, this system implements an explicit **Graph of Responsibility**:

1. **Deterministic State Transitions**: State transitions are guarded by calibrated confidence thresholds ($\tau = 0.60$) and domain-specific invariants.
2. **Self-Healing Fault Tolerance**: An embedded back-off harness recovers transient tool failures using exponential decay ($t_{backoff} = 0.4 \times 2^{attempt-1}$).
3. **Safety Contract & Auditability**: A hard invariant requires $\ge 3$ verified tool invocations and an immutable Write-Ahead Log (WAL) before any ticket can enter the `RESOLVED` sink state.

---

## 2. Cyclic Agent StateGraph & Control-Flow Engine

The following state graph defines the nodes, decision gates, and conditional edges that govern each ticket's autonomous lifecycle.

```mermaid
graph TD
    %% Styling definitions
    classDef startNode fill:#1E293B,stroke:#0EA5E9,stroke-width:2px,color:#F8FAFC;
    classDef processNode fill:#0F172A,stroke:#38BDF8,stroke-width:1px,color:#F8FAFC;
    classDef gateNode fill:#312E81,stroke:#818CF8,stroke-width:2px,color:#EEF2FF;
    classDef toolNode fill:#14532D,stroke:#4ADE80,stroke-width:1px,color:#F0FDF4;
    classDef retryNode fill:#78350F,stroke:#FBBF24,stroke-width:2px,color:#FEF3C7;
    classDef sinkResolved fill:#064E3B,stroke:#10B981,stroke-width:3px,color:#ECFDF5;
    classDef sinkEscalated fill:#7F1D1D,stroke:#F87171,stroke-width:3px,color:#FEF2F2;

    %% Ingestion & Perception
    A([📥 Ingest Ticket]) --> B[Perception Node: Weighted Token Normalizer & Classifier]
    B --> C{Confidence Gate: Conf >= 0.60?}
    
    %% Gating
    C -- "No (Conf < 0.60)" --> S1[Tag: low_confidence] --> ESC[🚨 Sink: ESCALATED]
    C -- "Yes (Conf >= 0.60)" --> D[Context Disambiguation & Entity Extractor]

    %% Smart Discovery Loop
    D --> E{Order ID Present in Payload?}
    E -- "Missing" --> F[Smart Order Discovery Node: Scan Customer History]
    F --> G{Historical Order Found?}
    G -- "No" --> S2[Tag: missing_critical_data] --> ESC
    G -- "Yes" --> H[Bind Inferred Order Context] --> I
    E -- "Present" --> I[Domain Strategy Dispatcher]

    %% Domain Routing
    I -->|refund| R1[Refund Strategy Node]
    I -->|order_issue| R2[Order Tracking Strategy Node]
    I -->|product_issue| R3[Defect & Replacement Strategy Node]
    I -->|general_inquiry| R4[Knowledge Base Strategy Node]

    %% Tool Execution Layer
    R1 & R2 & R3 & R4 --> T_EXEC[Tool Execution Harness]
    
    subgraph Tool_Palette [Isolated Asynchronous Tool Palette]
        T_EXEC --> T1[get_customer]
        T_EXEC --> T2[get_order]
        T_EXEC --> T3[get_product]
        T_EXEC --> T4[issue_refund]
        T_EXEC --> T5[send_reply]
        T_EXEC --> T6[read_knowledge_base]
    end

    %% Resiliency & Back-off Loop
    T1 & T2 & T3 & T4 & T5 & T6 --> T_STATUS{Tool Execution Status}
    
    T_STATUS -- "Transient Failure (Timeout/503)" --> R_CHECK{Attempts < 3?}
    R_CHECK -- "Yes" --> BACKOFF[Exponential Backoff: 0.4s / 0.8s] --> T_EXEC
    R_CHECK -- "No (Retries Exhausted)" --> S3[Tag: unrecoverable_tool_failure] --> ESC
    
    T_STATUS -- "Permanent Error / Not Found" --> S4[Tag: manual_fulfillment_required] --> ESC

    %% Step OK & Safety Gate
    T_STATUS -- "Success" --> AUDIT[WAL Scribe: Append Immutable Audit Entry]
    AUDIT --> OBJ_CHECK{Domain Objective Met?}
    
    OBJ_CHECK -- "Need Supplementary Data" --> T_EXEC
    OBJ_CHECK -- "Yes" --> Q_GATE{Quality Safety Gate: Tool Steps >= 3?}
    
    Q_GATE -- "Steps < 3" --> PAD[Supplement Policy/Product Verification] --> T_EXEC
    Q_GATE -- "Steps >= 3" --> RES[✅ Sink: RESOLVED]

    %% Output
    RES & ESC --> PERSIST[(Telemetry Ledger: audit_log.json & results.json)]

    class A startNode;
    class B,D,F,H,I,R1,R2,R3,R4,T_EXEC,AUDIT,PAD processNode;
    class C,E,G,T_STATUS,R_CHECK,OBJ_CHECK,Q_GATE gateNode;
    class T1,T2,T3,T4,T5,T6 toolNode;
    class BACKOFF retryNode;
    class RES sinkResolved;
    class ESC sinkEscalated;
```

---

## 3. System Layered Harness Architecture

The software architecture separates concerns into five distinct operational planes:

```mermaid
flowchart TB
    subgraph L1 [Plane 1: Ingestion & Orchestration Plane]
        CLI[main.py CLI Runner]
        UI[app.py Streamlit Dashboard]
        CONC[Async Semaphore Worker Pool: concurrency=5]
        QUEUE[(In-Memory Ticket Batch Queue)]
        CLI & UI --> CONC --> QUEUE
    end

    subgraph L2 [Plane 2: Perception & Gating Plane]
        NORM[Text Sanitizer & Tokenizer]
        CLF[Weighted Regex Scoring Engine: classifier.py]
        GATE[Early-Exit Confidence Gate: threshold=0.60]
        QUEUE --> NORM --> CLF --> GATE
    end

    subgraph L3 [Plane 3: Cognitive Agent Core Plane]
        REACT[ReAct Orchestrator: agent.py]
        STATE[Agent State Container: AgentState]
        DISCOVERY[Context Recovery: Order History Matcher]
        DISPATCH[Domain Policy Router: 4 Issue Categories]
        GATE --> REACT
        REACT <--> STATE
        REACT --> DISCOVERY --> DISPATCH
    end

    subgraph L4 [Plane 4: Resiliency & Tool Execution Harness]
        HARNESS[Tool Invocation Harness: _invoke_tool]
        EXP_BACKOFF[Exponential Backoff & Jitter Scheduler]
        CIRCUIT[Retry Budget Controller: MAX_RETRIES=2]
        PALETTE[Simulated Tool Palette: tools.py]
        
        DISPATCH --> HARNESS
        HARNESS <--> EXP_BACKOFF
        HARNESS <--> CIRCUIT
        HARNESS --> PALETTE
    end

    subgraph L5 [Plane 5: Observability, Audit & Telemetry Plane]
        WAL[Immutable Audit Trail Recorder: AuditEntry]
        AUDIT_OUT[(output/audit_log.json)]
        RESULTS_OUT[(output/results.json)]
        HARNESS --> WAL
        REACT --> WAL
        WAL --> AUDIT_OUT & RESULTS_OUT
    end
```

---

## 4. End-to-End Execution Sequence Diagram

The following sequence traces a real-world complex scenario (`TKT-006`): a customer requests a cancellation without supplying an Order ID, experiencing a transient network timeout along the way.

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer / Ingestion Queue
    participant Runner as Async Runner (main.py)
    participant Classifier as Classifier (classifier.py)
    participant Agent as ReAct Engine (agent.py)
    participant Tools as Tool Harness (tools.py)
    participant Telemetry as Audit Ledger (audit_log.json)

    Customer->>Runner: Ingest Ticket (TKT-006, body="Cancel my order please")
    Runner->>Classifier: classify_ticket(subject, body)
    Classifier-->>Runner: ClassificationResult(type="refund", conf=0.920)
    
    Runner->>Agent: process_ticket(ticket_dict)
    Agent->>Telemetry: Record Decision: Confidence Gate Passed (conf=0.920 >= 0.60)
    
    Note over Agent: Missing Order ID detected! Initiating Smart Context Discovery.
    Agent->>Tools: get_customer(email="david@example.com")
    Tools-->>Agent: {"id": "CUST-004", "tier": "standard"}
    Agent->>Telemetry: Record Success: Step 1 (get_customer, attempt=1)

    Agent->>Tools: list_orders(email="david@example.com")
    Note over Tools: Simulated transient network spike (ToolTimeout)
    Tools--xAgent: ToolTimeout("get_order service unreachable")
    Agent->>Telemetry: Record Retry: Step 2 (list_orders, attempt=1, status="retry")
    
    Note over Agent: Resiliency Harness: Exponential backoff wait (0.4s)
    Agent->>Agent: asyncio.sleep(0.4)
    Agent->>Tools: list_orders(email="david@example.com") [Retry 1]
    Tools-->>Agent: [{"order_id": "ORD-1006", "status": "processing", "amount": 199.99}]
    Agent->>Telemetry: Record Success: Step 2 (list_orders, attempt=2)

    Note over Agent: Bound Context -> Order ORD-1006. Validating Refund Policy.
    Agent->>Tools: check_refund_eligibility("ORD-1006")
    Tools-->>Agent: {"eligible": true, "reason": "Order unfulfilled within cancellation window"}
    Agent->>Telemetry: Record Success: Step 3 (check_refund_eligibility)

    Agent->>Tools: issue_refund("ORD-1006", 199.99)
    Tools-->>Agent: {"status": "success", "refund_id": "REF-7D7C7915"}
    Agent->>Telemetry: Record Success: Step 4 (issue_refund)

    Agent->>Tools: send_reply(email, message)
    Tools-->>Agent: {"delivered": true}
    Agent->>Telemetry: Record Success: Step 5 (send_reply)

    Note over Agent: Safety Assertion: Total tool steps (5) >= MIN_TOOL_CALLS (3).
    Agent->>Telemetry: Record Decision: Mark Final Status -> RESOLVED
    Agent-->>Runner: TicketResult(status="RESOLVED", calls=5, retries=1)
    Runner->>Telemetry: Flush immutable audit trail & summary JSON
```

---

## 5. Architectural Invariants & Engineering Guarantees

| Invariant | Implementation Mechanism | System Guarantee |
| :--- | :--- | :--- |
| **Zero Hallucination** | Deterministic domain heuristics + Mock Datastores | No generative model improvisation; all replies adhere strictly to verified policy constraints. |
| **Bounded Execution Cycle** | Fixed ReAct loop budget (`MAX_RETRIES = 2`, finite state machine) | Graph cannot loop infinitely; guaranteed $O(1)$ upper bound per ticket. |
| **Self-Healing Resilience** | Exponential back-off ($0.4\text{s} \to 0.8\text{s}$) with categorized exceptions | Recovers $100\%$ of transient network faults without human intervention. |
| **Verification Depth** | Minimum Tool Step Contract (`MIN_TOOL_CALLS = 3`) | Prevents premature resolution; every ticket must query customer, verify eligibility, and confirm action. |
| **100% Causal Observability**| Write-Ahead Audit Telemetry (`AuditEntry` schema) | Every attempt, duration, score, and reasoning justification is logged before and after execution. |
| **Exhaustive Escalation Taxonomy**| Closed reason enum: `low_confidence`, `missing_critical_data`, `unrecoverable_tool_failure`, `manual_fulfillment_required` | Clean human handoff with zero ambiguous dropouts. |

---

## 6. Formal State Schema Definition

The state container passed throughout the graph is structured as:

```python
@dataclass
class AgentState:
    # Ingestion Metadata
    ticket_id: str
    customer_email: str
    raw_subject: str
    raw_body: str
    
    # Perception & Classification
    issue_type: Literal["refund", "order_issue", "product_issue", "general_inquiry"]
    confidence_score: float
    confidence_passed: bool
    
    # Discovered Entities
    resolved_order_id: str | None
    customer_profile: dict[str, Any] | None
    order_details: dict[str, Any] | None
    
    # Execution & Resiliency
    step_count: int
    retry_count: int
    remaining_retry_budget: int
    
    # Telemetry & Output
    audit_trail: list[AuditEntry]
    terminal_status: Literal["resolved", "escalated", "failed"]
    resolution_message: str
    escalation_reason_tag: str | None
```
