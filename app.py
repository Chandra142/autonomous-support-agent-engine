"""
app.py

Interactive Web Application & Live Dashboard for AutoSupport Agent AI
Developed by Ram Chandra Gupta (@Chandra142)

Launch locally:
    streamlit run app.py
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from agent import process_ticket, TicketResult, AuditEntry, ESCALATION_THRESHOLD, MIN_TOOL_CALLS, MAX_RETRIES
import tools as T

# Page Configuration
st.set_page_config(
    page_title="AutoSupport Agent AI | Ram Chandra Gupta",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        color: #1E293B;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .badge-tag {
        display: inline-block;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 0.4rem;
        margin-bottom: 0.5rem;
    }
    .badge-blue { background-color: #E0F2FE; color: #0369A1; }
    .badge-green { background-color: #DCFCE7; color: #15803D; }
    .badge-purple { background-color: #F3E8FF; color: #7E22CE; }
    .badge-amber { background-color: #FEF3C7; color: #B45309; }
    .stMetric {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 1rem;
        border-radius: 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

@st.cache_data
def load_default_tickets() -> list[dict]:
    tickets_path = DATA_DIR / "tickets.json"
    if tickets_path.exists():
        with open(tickets_path, "r", encoding="utf-8") as f:
            tickets = json.load(f)
            for t in tickets:
                if "id" not in t and "ticket_id" in t:
                    t["id"] = t["ticket_id"]
                if "customer_email" not in t and "email" in t:
                    t["customer_email"] = t["email"]
            return tickets
    return []

# Sidebar Navigation & Settings
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bot.png", width=70)
    st.markdown("### **AutoSupport Agent AI**")
    st.markdown("**Author:** Ram Chandra Gupta ([@Chandra142](https://github.com/Chandra142))")
    
    st.markdown("---")
    st.markdown("#### ⚙️ Agent Parameters")
    concurrency = st.slider("Concurrency Limit", min_value=1, max_value=10, value=5, help="Number of tickets processed in parallel.")
    threshold = st.slider("Escalation Gate Threshold", min_value=0.4, max_value=0.8, value=ESCALATION_THRESHOLD, step=0.05, help="Confidence below this triggers safe human escalation.")
    
    st.markdown("---")
    st.markdown("#### 🔗 Repository & Docs")
    st.markdown("- [GitHub Repository](https://github.com/Chandra142/autonomous-support-agent-engine)")
    st.markdown("- [Failure Modes Documentation](docs/failure_modes.md)")
    st.markdown("- [Architecture Diagram](architecture_diagram.md)")
    
    st.markdown("---")
    st.caption("Engineered with native Python standard library with full ReAct loop and audit telemetry.")

# Title and Badges
st.markdown('<div class="main-title">🤖 AutoSupport Agent AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Production-Grade Autonomous Support Engine with Smart Context Recovery & Immutable Audit Trail</div>', unsafe_allow_html=True)

st.markdown("""
<div>
    <span class="badge-tag badge-green">70% Resolution Benchmark</span>
    <span class="badge-tag badge-blue">ReAct Reasoning Loop</span>
    <span class="badge-tag badge-purple">Zero LLM Hallucinations</span>
    <span class="badge-tag badge-amber">Self-Healing Retry x2</span>
</div>
""", unsafe_allow_html=True)

# Session State Initialization
if "results" not in st.session_state:
    st.session_state.results = []
if "batch_run_time" not in st.session_state:
    st.session_state.batch_run_time = 0.0

# Tabs
tab_batch, tab_audit, tab_sandbox, tab_kb = st.tabs([
    "📋 Batch Queue Runner",
    "🔍 Granular Audit Trail",
    "🧪 Test Custom Ticket",
    "📚 Knowledge Base & Architecture"
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: BATCH QUEUE RUNNER
# ─────────────────────────────────────────────────────────────────────────────
with tab_batch:
    tickets_data = load_default_tickets()
    st.markdown(f"Loaded **{len(tickets_data)} tickets** from `data/tickets.json`.")
    
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        start_batch = st.button("▶ Run Autonomous Batch", type="primary", use_container_width=True)
    with col_info:
        st.info(f"Targeting 20 production scenarios: missing order IDs, return windows, defective items, ambiguous queries.")

    async def run_batch_simulation(tickets: list[dict], conc: int):
        sem = asyncio.Semaphore(conc)
        progress_bar = st.progress(0, text="Initializing async worker pool...")
        status_text = st.empty()
        
        results = []
        completed = 0
        total = len(tickets)
        
        async def worker(tkt: dict):
            nonlocal completed
            async with sem:
                res = await process_ticket(tkt)
                completed += 1
                progress_bar.progress(completed / total, text=f"Processed {completed}/{total} tickets ({tkt.get('id', 'TKT')})...")
                status_text.caption(f"Last processed: **{res.ticket_id}** ➔ **{res.final_status.upper()}** ({res.successful_tool_calls} tool calls)")
                return res
        
        t0 = time.monotonic()
        tasks = [worker(t) for t in tickets]
        results = await asyncio.gather(*tasks)
        elapsed = round(time.monotonic() - t0, 2)
        progress_bar.progress(1.0, text=f"Completed {total} tickets in {elapsed}s!")
        return results, elapsed

    if start_batch:
        with st.spinner("Processing tickets concurrently..."):
            results, elapsed = asyncio.run(run_batch_simulation(tickets_data, concurrency))
            st.session_state.results = results
            st.session_state.batch_run_time = elapsed
            st.success(f"Successfully processed {len(results)} tickets in {elapsed}s!")

    # Display Metrics if results exist
    if st.session_state.results:
        results = st.session_state.results
        total_count = len(results)
        resolved_count = sum(1 for r in results if r.final_status == "resolved")
        escalated_count = sum(1 for r in results if r.final_status == "escalated")
        total_tool_calls = sum(r.successful_tool_calls for r in results)
        total_retries = sum(r.retry_count for r in results)
        res_rate = (resolved_count / total_count * 100) if total_count else 0
        
        st.markdown("### 📊 Execution Telemetry")
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Tickets", total_count)
        m2.metric("Autonomous Resolution", f"{res_rate:.1f}%", f"{resolved_count} resolved")
        m3.metric("Safe Escalations", f"{(escalated_count/total_count*100):.1f}%", f"{escalated_count} escalated")
        m4.metric("Tool Invocations", total_tool_calls)
        m5.metric("Recovered Retries", total_retries)
        m6.metric("Processing Time", f"{st.session_state.batch_run_time}s")
        
        # Table of Results
        st.markdown("### 📑 Resolution Matrix")
        table_rows = []
        for r in results:
            table_rows.append({
                "Ticket ID": r.ticket_id,
                "Customer": r.customer_email,
                "Issue Type": r.issue_type,
                "Confidence": f"{r.final_confidence:.3f}",
                "Status": "✅ RESOLVED" if r.final_status == "resolved" else "⚠️ ESCALATED",
                "Tool Calls": r.successful_tool_calls,
                "Retries": r.retry_count,
                "Resolution Summary": r.resolution_message
            })
        df = pd.DataFrame(table_rows)
        
        # Filtering options
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            status_filter = st.selectbox("Filter by Status", ["All", "RESOLVED", "ESCALATED"])
        with filter_col2:
            issue_filter = st.selectbox("Filter by Issue Type", ["All"] + sorted(list(set(r.issue_type for r in results))))
            
        filtered_df = df
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df["Status"].str.contains(status_filter)]
        if issue_filter != "All":
            filtered_df = filtered_df[filtered_df["Issue Type"] == issue_filter]
            
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: GRANULAR AUDIT TRAIL
# ─────────────────────────────────────────────────────────────────────────────
with tab_audit:
    st.markdown("### 🔍 Step-by-Step Immutable Audit Explorer")
    st.markdown("Every internal decision, external tool call, backoff retry, and parameter payload is permanently logged.")
    
    if not st.session_state.results:
        st.info("Run the batch simulation in Tab 1 or test a custom ticket in Tab 3 to view audit logs.")
    else:
        ticket_options = [r.ticket_id for r in st.session_state.results]
        selected_tkt_id = st.selectbox("Select Ticket to Inspect:", ticket_options, index=5 if len(ticket_options) > 5 else 0)
        
        selected_result = next((r for r in st.session_state.results if r.ticket_id == selected_tkt_id), None)
        
        if selected_result:
            col_info1, col_info2, col_info3 = st.columns(3)
            col_info1.markdown(f"**Customer:** `{selected_result.customer_email}`")
            col_info2.markdown(f"**Classification:** `{selected_result.issue_type}` (conf: `{selected_result.final_confidence:.3f}`)")
            badge = "🟢 RESOLVED" if selected_result.final_status == "resolved" else "🟡 ESCALATED"
            col_info3.markdown(f"**Final Outcome:** {badge}")
            
            st.markdown(f"**Outcome Reason / Reply:** {selected_result.resolution_message}")
            
            st.markdown("#### Audit Telemetry Steps")
            audit_records = []
            for idx, entry in enumerate(selected_result.audit_trail, 1):
                audit_records.append({
                    "Step": idx,
                    "Timestamp": entry.timestamp.split("T")[-1][:8] if "T" in entry.timestamp else entry.timestamp,
                    "Step Name": entry.step_name,
                    "Tool": entry.tool_name or "-",
                    "Status": entry.status.upper(),
                    "Attempt": entry.attempt,
                    "Duration (ms)": f"{entry.duration_ms:.1f}" if entry.duration_ms else "-",
                    "Reason": entry.reason,
                    "Payload": json.dumps(entry.input or entry.output or {}, ensure_ascii=False)
                })
            
            audit_df = pd.DataFrame(audit_records)
            st.dataframe(audit_df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: TEST CUSTOM TICKET
# ─────────────────────────────────────────────────────────────────────────────
with tab_sandbox:
    st.markdown("### 🧪 Live Agent Sandbox")
    st.markdown("Submit a synthetic or custom customer support request to evaluate the agent's real-time reasoning.")
    
    with st.form("custom_ticket_form"):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_email = st.text_input("Customer Email", value="alice@example.com", help="Email associated with customer account.")
            c_id = st.text_input("Ticket ID", value="TKT-001", help="Standard registered IDs: TKT-001 to TKT-020, or custom format TKT-XXXX.")
        with col_c2:
            c_order_id = st.text_input("Order ID (Optional - leave blank to test smart lookup)", value="")
            c_subject = st.text_input("Subject", value="Cancel my recent order please")
            
        c_body = st.text_area("Ticket Body", value="Hi, I just placed an order an hour ago and I want to cancel it. My email is alice@example.com. Please process refund.", height=120)
        
        submit_custom = st.form_submit_button("⚡ Run Autonomous Resolution", type="primary")

    if submit_custom:
        custom_ticket = {
            "id": c_id.strip(),
            "customer_email": c_email.strip(),
            "order_id": c_order_id.strip() or None,
            "subject": c_subject.strip(),
            "body": c_body.strip()
        }
        
        with st.spinner("Agent is validating ticket ID, reasoning, classifying, and executing tool actions..."):
            t0 = time.monotonic()
            custom_res = asyncio.run(process_ticket(custom_ticket))
            el = round((time.monotonic() - t0) * 1000, 2)
            
        if custom_res.final_status == "resolved":
            st.success(f"Processing finished in {el} ms — Ticket Resolved!")
        else:
            st.warning(f"Processing finished in {el} ms — Ticket Escalated to Human Support!")
        
        # Display Result
        res_col1, res_col2 = st.columns([1, 2])
        with res_col1:
            st.metric("Final Status", custom_res.final_status.upper())
            st.metric("Issue Type", custom_res.issue_type)
            st.metric("Confidence", f"{custom_res.final_confidence:.3f}")
            st.metric("Tool Invocations", custom_res.successful_tool_calls)
        with res_col2:
            st.markdown("#### Agent Resolution Outcome")
            if custom_res.final_status == "resolved":
                st.info(custom_res.resolution_message)
            else:
                st.warning(custom_res.resolution_message)
            
            if custom_res.error:
                st.error(f"⚠️ **Validation Detail:** {custom_res.error}")
            
            st.markdown("#### Tool Execution Timeline")
            for i, step in enumerate(custom_res.audit_trail, 1):
                icon = "⚙️" if step.status == "success" else ("🔄" if step.status == "retry" else ("🚨" if step.status == "error" else "🧠"))
                st.caption(f"{icon} **Step {i}: {step.step_name}** | Status: `{step.status}` | Reason: _{step.reason}_")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: KNOWLEDGE BASE & ARCHITECTURE
# ─────────────────────────────────────────────────────────────────────────────
with tab_kb:
    st.markdown("### 📚 Knowledge Base & Architecture Reference")
    
    tab_arch_sub, tab_kb_sub, tab_data_sub = st.tabs(["Architecture Overview", "Knowledge Base Document", "Mock Datastores"])
    
    with tab_arch_sub:
        arch_md_path = BASE_DIR / "architecture_diagram.md"
        if arch_md_path.exists():
            st.markdown(arch_md_path.read_text(encoding="utf-8"))
        else:
            arch_path = BASE_DIR / "architecture.png"
            if arch_path.exists():
                st.image(str(arch_path), caption="End-to-End Autonomous Agentic Architecture", use_container_width=True)
                
    with tab_kb_sub:
        kb_text = T.get_knowledge_base()
        st.markdown(kb_text)
        
    with tab_data_sub:
        customers, orders, products = T.get_data()
        st.markdown("#### Customers Database")
        st.json(customers[:3] if isinstance(customers, list) else customers)
        st.markdown("#### Orders Database")
        st.json(orders[:3] if isinstance(orders, list) else orders)
        st.markdown("#### Products Database")
        st.json(products)
