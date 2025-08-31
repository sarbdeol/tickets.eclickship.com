# app.py — Tickets Tracker (Advanced, ready to deploy)
# ---------------------------------
import datetime as dt
import sqlite3
from pathlib import Path
from html import escape as _esc
import pandas as pd
import streamlit as st
import pytz

DB_PATH = Path("tickets.db")

# --- Constants ---
USERS = ["Sam", "Vinny", "Daiana", "Flora", "Geetika", "Dharminder", "Graciela", "Ashu"]
COMMUNICATION = ["Informed Customer", "Waiting for Customer Response", "On Hold as per Customer"]

PRIORITY = ["Today", "Today 2", "Tomorrow", "2 days"]
PRIORITY_COLORS = {"Today": "#ff9999", "Today 2": "#ffff66", "Tomorrow": "#66b3ff", "2 days": "#bfbfbf"}
STATUS = ["Open", "Started", "Completed", "Waiting on Customer", "On Hold", "Gated"]
STATUS_COLORS = {"Open": "#c00000", "Started": "#ed7d31", "Completed": "#00b050",
                 "Waiting on Customer": "#f1c232", "On Hold": "#7f7f7f", "Gated": "#7030a0"}

eastern = pytz.timezone("US/Eastern")

# ---------------- Database ----------------
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_entered TEXT NOT NULL,
                time_entered TEXT NOT NULL,
                communication TEXT,
                entered_by TEXT,
                assigned_to TEXT,
                fba_customer TEXT,
                instructions_order_id TEXT,
                priority TEXT,
                due_date TEXT,
                status TEXT,
                notes TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS deleted_tickets (
                id INTEGER PRIMARY KEY,
                date_entered TEXT NOT NULL,
                time_entered TEXT NOT NULL,
                communication TEXT,
                entered_by TEXT,
                assigned_to TEXT,
                fba_customer TEXT,
                instructions_order_id TEXT,
                priority TEXT,
                due_date TEXT,
                status TEXT,
                notes TEXT
            )
            """
        )
        con.commit()


def insert_ticket(row: dict):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO tickets (
                date_entered,time_entered,communication,entered_by,assigned_to,
                fba_customer,instructions_order_id,priority,due_date,status,notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            tuple(row.values()),
        )
        con.commit()
        return cur.lastrowid


def update_ticket(ticket_id: int, updates: dict):
    if not updates:
        return
    cols = [f"{k}=?" for k in updates.keys()]
    vals = list(updates.values()) + [ticket_id]
    with sqlite3.connect(DB_PATH) as con:
        con.execute(f"UPDATE tickets SET {', '.join(cols)} WHERE id=?", vals)
        con.commit()


def delete_tickets(ids):
    if not ids:
        return
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        for ticket_id in ids:
            cur.execute("INSERT INTO deleted_tickets SELECT * FROM tickets WHERE id=?", (int(ticket_id),))
            cur.execute("DELETE FROM tickets WHERE id=?", (int(ticket_id),))
        con.commit()


def recover_tickets(ids):
    if not ids:
        return
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        for ticket_id in ids:
            cur.execute("INSERT INTO tickets SELECT * FROM deleted_tickets WHERE id=?", (int(ticket_id),))
            cur.execute("DELETE FROM deleted_tickets WHERE id=?", (int(ticket_id),))
        con.commit()


def load_tickets(table: str = "tickets") -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC", con)


# ---------------- Helpers ----------------
def color_badge(text: str, color_map: dict, dark_text: bool = False) -> str:
    color = color_map.get(text, "#ddd")
    fg = "#000" if dark_text else "#fff"
    return (
        f"<span style='background:{color};color:{fg};padding:4px 10px;border-radius:20px;"
        f"font-size:13px;font-weight:600;'>{_esc(text)}</span>"
    )


def calculate_due_date(priority: str) -> str:
    today = dt.datetime.now(eastern)
    if priority in ("Today", "Today 2"):
        return today.strftime("%m/%d/%Y")
    if priority == "Tomorrow":
        return (today + dt.timedelta(days=1)).strftime("%m/%d/%Y")
    if priority == "2 days":
        return (today + dt.timedelta(days=2)).strftime("%m/%d/%Y")
    return today.strftime("%m/%d/%Y")


# ---------------- Table Renderer (HTML table + modal note) ----------------
def render_table(df: pd.DataFrame, deleted: bool = False):
    # --- Filters ---
    with st.expander("🔍 Filter", expanded=False):
        fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 2])
        with fc1:
            assignee = st.selectbox("Assigned To", ["All"] + USERS, key=f"assignee_{'del' if deleted else 'act'}")
        with fc2:
            status_val = st.selectbox("Status", ["All"] + STATUS, key=f"status_{'del' if deleted else 'act'}")
        with fc3:
            priority_val = st.selectbox("Priority", ["All"] + PRIORITY, key=f"priority_{'del' if deleted else 'act'}")
        with fc4:
            query = st.text_input("Search (customer, order id, note, etc.)", key=f"q_{'del' if deleted else 'act'}").strip()

    filtered = df.copy()
    if assignee != "All":
        filtered = filtered[filtered["assigned_to"] == assignee]
    if status_val != "All":
        filtered = filtered[filtered["status"] == status_val]
    if priority_val != "All":
        filtered = filtered[filtered["priority"] == priority_val]
    if query:
        q = query.lower()
        mask = filtered.apply(lambda row: any(q in str(val).lower() for val in row.values), axis=1)
        filtered = filtered[mask]

    # --- Bulk actions (multiselect) ---
    st.write("**Bulk actions**")
    table_tag = "deleted" if deleted else "active"

    option_labels = [f"#{r['id']} • {r['fba_customer']} • {r['status']}" for _, r in filtered.iterrows()]
    label_to_id = {f"#{r['id']} • {r['fba_customer']} • {r['status']}": int(r["id"]) for _, r in filtered.iterrows()}

    sleft, sright = st.columns([3, 2])
    multi_key = f"bulk_{table_tag}_opts"

    with sleft:
        st.multiselect("Select tickets:", option_labels, key=multi_key)
    with sright:
        _, _, cc = st.columns([1, 1, 2])
        if not deleted:
            if cc.button("🗑️ Delete selected", type="primary", key=f"delbtn_{table_tag}"):
                ids = [label_to_id[l] for l in st.session_state.get(multi_key, [])]
                if ids:
                    delete_tickets(ids)
                    st.success(f"Deleted {len(ids)} ticket(s).")
                    st.rerun()
                else:
                    st.warning("No tickets selected for deletion.")
        else:
            if cc.button("♻️ Recover selected", type="primary", key=f"recbtn_{table_tag}"):
                ids = [label_to_id[l] for l in st.session_state.get(multi_key, [])]
                if ids:
                    recover_tickets(ids)
                    st.success(f"Recovered {len(ids)} ticket(s).")
                    st.rerun()
                else:
                    st.warning("No tickets selected for recovery.")

    st.divider()

    if filtered.empty:
        st.info("No records match your filters.")
        return

    def esc(x):
        return _esc(str(x or ""))

    rows_html = ""
    for _, r in filtered.iterrows():
        pr_badge = color_badge(r["priority"], PRIORITY_COLORS, dark_text=True)
        st_badge = color_badge(r["status"], STATUS_COLORS)
        note_text = str(r.get("notes", "") or "")
        safe_note = note_text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        note_btn = f"<button type='button' onclick=\"openNote('{safe_note}')\">📝 View</button>" if note_text else "📝 No Note"
        rows_html += f"""
        <tr>
            <td>{esc(r['id'])}</td>
            <td>{esc(r['date_entered'])}</td>
            <td>{esc(r['time_entered'])}</td>
            <td>{esc(r['entered_by'])}</td>
            <td>{esc(r['assigned_to'])}</td>
            <td>{esc(r['fba_customer'])}</td>
            <td>{esc(r['instructions_order_id'])}</td>
            <td>{pr_badge}</td>
            <td>{esc(r['due_date'])}</td>
            <td>{st_badge}</td>
            <td>{note_btn}</td>
            <td>{esc(r['communication'])}</td>
        </tr>
        """

    html = f"""
    <style>
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 6px; }}
    th, td {{ border: 1px solid #e6e6e6; padding: 8px; text-align: center; }}
    th {{ background: #f8f9fa; font-weight: 700; }}
    tr:nth-child(even) {{ background: #fafafa; }}
    tr:hover {{ background: #eef6ff; }}
    button {{ padding: 4px 10px; border-radius: 6px; cursor: pointer; border: none; background: #007bff; color: #fff; font-size: 12px; }}
    button:hover {{ opacity: .9; }}

    .modal {{ display:none; position:fixed; z-index:1000; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,.55); }}
    .modal-content {{ background:#fff; margin:8% auto; padding:18px; border-radius:10px; width:60%; max-width:640px; position:relative; box-shadow:0 8px 24px rgba(0,0,0,.25); }}
    .close {{ position:absolute; right:12px; top:8px; font-size:26px; color:#666; cursor:pointer; }}
    #noteText {{ white-space:pre-wrap; text-align:left; padding:10px; background:#f8f9fa; border-radius:6px; max-height:340px; overflow:auto; }}
    </style>

    <table>
      <thead>
        <tr>
          <th>ID</th><th>Date</th><th>Time</th><th>Entered By</th><th>Assigned</th>
          <th>Customer</th><th>Order ID</th><th>Priority</th><th>Due</th><th>Status</th><th>Notes</th><th>Comm</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <div id=\"noteModal\" class=\"modal\">
      <div class=\"modal-content\">
        <span class=\"close\" onclick=\"closeModal()\">&times;</span>
        <h3>📝 Ticket Note</h3>
        <div id=\"noteText\"></div>
        <div style=\"text-align:right; margin-top:10px;\"><button onclick=\"closeModal()\" style=\"background:#6c757d\">Close</button></div>
      </div>
    </div>

    <script>
    function openNote(t) {{
      if (!t || t.trim() === '') {{ alert('No note available for this ticket.'); return; }}
      document.getElementById('noteText').innerText = t;
      document.getElementById('noteModal').style.display = 'block';
    }}
    function closeModal() {{ document.getElementById('noteModal').style.display = 'none'; }}
    window.onclick = function(e) {{ const m = document.getElementById('noteModal'); if (e.target === m) closeModal(); }}
    document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeModal(); }});
    </script>
    """
    
    st.components.v1.html(html, height=560, scrolling=True)


# ---------------- Pages ----------------
def dashboard():
    st.subheader("📊 Dashboard")
    df = load_tickets("tickets")
    render_table(df, deleted=False)


def add_new():
    st.subheader("➕ Add Ticket")
    # show success message after rerun
    if st.session_state.pop("flash_add_success", False):
        st.success("✅ Ticket added.")
    now = dt.datetime.now(eastern)
    with st.form("new_ticket"):
        # All defaults blank
        ent = st.selectbox("Entered By", [""] + USERS, index=0, key="add_ent")
        own = st.selectbox("Assigned To", [""] + USERS, index=0, key="add_own")
        pr = st.selectbox("Priority", [""] + PRIORITY, index=0, key="add_pr")
        cust = st.text_input("FBA Customer", value="", key="add_cust")
        stt = st.selectbox("Status", [""] + STATUS, index=0, key="add_status")
        instr = st.text_area("Instructions / Order ID", value="", key="add_instr")
        notes = st.text_area("Notes", value="", key="add_notes")
        comm = st.selectbox("Comm", [""] + COMMUNICATION, index=0, key="add_comm")

        submitted = st.form_submit_button("Add")
        if submitted:
            due_date = calculate_due_date(pr) if pr else ""
            payload = dict(
                date_entered=now.strftime("%m/%d/%Y"),
                time_entered=now.strftime("%I:%M %p"),
                communication=comm,
                entered_by=ent,
                assigned_to=own,
                fba_customer=cust,
                instructions_order_id=instr,
                priority=pr,
                due_date=due_date,
                status=stt,
                notes=notes,
            )
            insert_ticket(payload)
            # Clear fields so the form is blank again
            for k in ["add_ent","add_own","add_pr","add_cust","add_status","add_instr","add_notes","add_comm"]:
                if k in st.session_state:
                    del st.session_state[k]
            # set flash flag so success shows after rerun
            st.session_state["flash_add_success"] = True
            st.rerun()
def edit_existing():
    st.subheader("✏️ Edit Ticket")
    df = load_tickets("tickets")
    if df.empty:
        st.info("No tickets to edit.")
        return

    ids = df["id"].tolist()
    sel_id = st.selectbox("Select Ticket ID", ids)
    row = df[df["id"] == sel_id].iloc[0].to_dict()

    # helper: safe index into option lists
    def _idx(opts, val):
        v = "" if val is None else str(val)
        return opts.index(v) if v in opts else 0

    with st.form("edit_ticket"):
        # include blank first so legacy/empty values work
        ent_opts  = [""] + USERS
        own_opts  = [""] + USERS
        pr_opts   = [""] + PRIORITY
        stt_opts  = [""] + STATUS
        comm_opts = [""] + COMMUNICATION

        ent   = st.selectbox("Entered By", ent_opts,  index=_idx(ent_opts,  row.get("entered_by")))
        own   = st.selectbox("Assigned To", own_opts,  index=_idx(own_opts,  row.get("assigned_to")))
        pr    = st.selectbox("Priority",    pr_opts,   index=_idx(pr_opts,   row.get("priority")))
        cust  = st.text_input("FBA Customer", value=row.get("fba_customer", "") or "")
        stt   = st.selectbox("Status",      stt_opts, index=_idx(stt_opts,  row.get("status")))
        instr = st.text_area("Instructions / Order ID", value=row.get("instructions_order_id", "") or "")
        notes = st.text_area("Notes", value=row.get("notes", "") or "")
        comm  = st.selectbox("Comm",        comm_opts, index=_idx(comm_opts, row.get("communication")))

        save = st.form_submit_button("Save")
        if save:
            update_ticket(
                sel_id,
                dict(
                    communication=comm,
                    entered_by=ent,
                    assigned_to=own,
                    fba_customer=cust,
                    instructions_order_id=instr,
                    priority=pr,
                    due_date=calculate_due_date(pr) if pr else "",
                    status=stt,
                    notes=notes,
                ),
            )
            st.success(f"✅ Ticket #{sel_id} updated.")
            st.rerun()


def deleted_records():
    st.subheader("🗑️ Deleted Records")
    df = load_tickets("deleted_tickets")
    render_table(df, deleted=True)


# ---------------- Main ----------------
def main():
    st.set_page_config(page_title="customer Order Tracker", layout="wide")
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] .block-container {
            padding: 1rem !important;
            max-width: 100% !important;
        }
        .stTabs [data-baseweb="tab-list"] { gap: .25rem; }
        .stTabs [data-baseweb="tab"] { padding: 6px 10px; }
        h1, h2, h3 { margin-top: .25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🎟️ customer Order Tracker")
    init_db()

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "➕ Add New", "✏️ Edit Existing", "🗑️ Deleted Records"])
    with tab1:
        dashboard()
    with tab2:
        add_new()
    with tab3:
        edit_existing()
    with tab4:
        deleted_records()


if __name__ == "__main__":
    main()
