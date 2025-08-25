# app.py
import datetime as dt
from datetime import date
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import pytz

DB_PATH = Path("tickets.db")

# Users & Assignment
USERS = ["Sam", "Vinny", "Daiana", "Flora", "Geetika", "Dharminder", "Graciela", "Ashu"]
COMMUNICATION = ["Informed Customer", "Waiting for Customer Response", "On Hold as per Customer"]

# Priorities
PRIORITY = ["Today", "Today 2", "Tomorrow", "2 days"]
PRIORITY_COLORS = {
    "Today": "#ff9999",       # Light Red
    "Today 2": "#ffff66",     # Yellow
    "Tomorrow": "#66b3ff",    # Blue
    "2 days": "#bfbfbf",      # Grey
}

# Status
STATUS = [
    "Open (Default)",
    "Started",
    "Completed",
    "Waiting on Customer",
    "On Hold",
    "Gated"
]
STATUS_COLORS = {
    "Open (Default)": "#c00000",
    "Started": "#ed7d31",
    "Completed": "#00b050",
    "Waiting on Customer": "#f1c232",
    "On Hold": "#7f7f7f",
    "Gated": "#7030a0",
}

# Timezone
eastern = pytz.timezone("US/Eastern")

# ---------------- Database ----------------
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
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
        """)
        con.commit()

def insert_ticket(row: dict) -> int:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO tickets (
                date_entered, time_entered, communication, entered_by, assigned_to,
                fba_customer, instructions_order_id, priority, due_date, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(row.values()))
        con.commit()
        return cur.lastrowid

def update_ticket(ticket_id: int, updates: dict):
    cols = [f"{k}=?" for k in updates.keys()]
    vals = list(updates.values()) + [ticket_id]
    with sqlite3.connect(DB_PATH) as con:
        con.execute(f"UPDATE tickets SET {', '.join(cols)} WHERE id=?", vals)
        con.commit()

def delete_ticket(ticket_id: int):
    with sqlite3.connect(DB_PATH) as con:
        con.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
        con.commit()

def load_tickets(where_clause="", params=()):
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(
            f"SELECT * FROM tickets {where_clause} ORDER BY id DESC", con, params=params
        )
    # Backward compatibility: old DB with attention_owner
    if "attention_owner" in df.columns and "assigned_to" not in df.columns:
        df.rename(columns={"attention_owner": "assigned_to"}, inplace=True)
    return df

# ---------------- Helpers ----------------
def color_badge(text: str, color_map: dict) -> str:
    color = color_map.get(text, "#444")
    return f"""
    <span style="
        background:{color};
        color:#fff;
        padding:4px 12px;
        border-radius:20px;
        font-size:13px;
        font-weight:600;
        display:inline-block;
        min-width:80px;
        text-align:center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    ">{text}</span>
    """

def render_table(df: pd.DataFrame):
    if df.empty:
        st.info("No tickets yet.")
        return

    rows = []
    for _, r in df.iterrows():
        priority = color_badge(r["priority"], PRIORITY_COLORS)
        status = color_badge(r["status"], STATUS_COLORS)
        rows.append(f"""
            <tr>
                <td>{r['id']}</td>
                <td>{r['date_entered']}</td>
                <td>{r['time_entered']}</td>
                <td>{r['communication']}</td>
                <td>{r['entered_by']}</td>
                <td>{r['assigned_to']}</td>
                <td>{r['fba_customer']}</td>
                <td>{r['instructions_order_id']}</td>
                <td>{priority}</td>
                <td>{r['due_date']}</td>
                <td>{status}</td>
                <td>{r['notes']}</td>
            </tr>
        """)

    html = f"""
    <style>
    table {{
        width: 100%;
        border-collapse: collapse;
        font-family: 'Segoe UI', Tahoma, sans-serif;
        font-size: 14px;
    }}
    th, td {{
        border: 1px solid #ddd;
        padding: 10px;
        text-align: center;
        vertical-align: middle;
    }}
    th {{
        background-color: #f8f9fa;
        font-weight: bold;
        color: #333;
        position: sticky;
        top: 0;
        z-index: 2;
    }}
    tr:nth-child(even) {{ background-color: #f9f9f9; }}
    tr:hover {{ background-color: #eef6ff; }}
    td:nth-child(8) {{ min-width: 250px; white-space: normal; }}
    td:nth-child(12) {{ white-space: normal; }}
    </style>

    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Date Entered</th>
                <th>Time Entered</th>
                <th>Communication</th>
                <th>Entered By</th>
                <th>Assigned To</th>
                <th>FBA Customer</th>
                <th>Instructions/Order ID</th>
                <th>Priority</th>
                <th>Due Date</th>
                <th>Status</th>
                <th>Notes</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """

    st.components.v1.html(html, height=600, scrolling=True)

# ---------------- Pages ----------------
def dashboard():
    st.subheader("📊 Dashboard")
    df = load_tickets()
    render_table(df)

def add_or_edit():
    st.subheader("📝 Add / Edit Tickets")
    mode = st.radio("Mode", ["Add New", "Edit Existing"], horizontal=True)

    if mode == "Edit Existing":
        df_all = load_tickets()
        ids = df_all["id"].tolist()
        if not ids:
            st.info("No tickets to edit. Switch to 'Add New'.")
            return
        sel_id = st.selectbox("Select Ticket ID", ids)
        row = df_all[df_all["id"] == sel_id].iloc[0].to_dict()
    else:
        sel_id = None
        now = dt.datetime.now(eastern)
        row = {
            "date_entered": now.strftime("%m/%d/%Y"),
            "time_entered": now.strftime("%I:%M %p"),
            "communication": COMMUNICATION[0],
            "entered_by": USERS[0],
            "assigned_to": USERS[0],
            "fba_customer": "",
            "instructions_order_id": "",
            "priority": PRIORITY[0],
            "due_date": now.strftime("%m/%d/%Y"),
            "status": STATUS[0],
            "notes": "",
        }

    with st.form("ticket_form", clear_on_submit=False):
        c1, c2, c3 = st.columns([1,1,1])
        with c1: st.text_input("Date Entered", value=row["date_entered"], disabled=True)
        with c2: st.text_input("Time Entered", value=row["time_entered"], disabled=True)
        with c3: due = st.date_input("Due Date", value=dt.datetime.strptime(row["due_date"], "%m/%d/%Y").date())

        c4, c5, c6 = st.columns([1,1,1])
        with c4: comm = st.selectbox("Communication", COMMUNICATION, index=COMMUNICATION.index(row["communication"]) if row["communication"] in COMMUNICATION else 0)
        with c5: ent = st.selectbox("Entered By", USERS, index=USERS.index(row["entered_by"]) if row["entered_by"] in USERS else 0)
        with c6: own = st.selectbox("Assigned To", USERS, index=USERS.index(row["assigned_to"]) if row["assigned_to"] in USERS else 0)

        c7, c8 = st.columns([1,1])
        with c7: pr = st.selectbox("Priority", PRIORITY, index=PRIORITY.index(row["priority"]) if row["priority"] in PRIORITY else 0)
        with c8: stt = st.selectbox("Status", STATUS, index=STATUS.index(row["status"]) if row["status"] in STATUS else 0)

        # Auto-set due_date
        if pr == "Today": due = date.today()
        elif pr == "Today 2": due = date.today()
        elif pr == "Tomorrow": due = date.today() + dt.timedelta(days=1)
        elif pr == "2 days": due = date.today() + dt.timedelta(days=2)

        cust = st.text_input("FBA Customer", value=row["fba_customer"])
        instr = st.text_area("Instructions / Order ID", value=row["instructions_order_id"], height=80)
        notes = st.text_area("Notes", value=row["notes"], height=200)

        if mode == "Add New":
            submitted = st.form_submit_button("➕ Add Ticket", use_container_width=True)
            if submitted:
                now = dt.datetime.now(eastern)
                payload = dict(
                    date_entered=now.strftime("%m/%d/%Y"),
                    time_entered=now.strftime("%I:%M %p"),
                    communication=comm,
                    entered_by=ent,
                    assigned_to=own,
                    fba_customer=cust,
                    instructions_order_id=instr,
                    priority=pr,
                    due_date=due.strftime("%m/%d/%Y"),
                    status=stt,
                    notes=notes
                )
                new_id = insert_ticket(payload)
                st.success(f"✅ Ticket #{new_id} added.")
                st.rerun()
        else:
            col_save, col_delete = st.columns([2,1])
            with col_save: save_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)
            with col_delete: delete_btn = st.form_submit_button("🗑️ Delete", use_container_width=True)

            if save_btn:
                updates = dict(
                    communication=comm,
                    entered_by=ent,
                    assigned_to=own,
                    fba_customer=cust,
                    instructions_order_id=instr,
                    priority=pr,
                    due_date=due.strftime("%m/%d/%Y"),
                    status=stt,
                    notes=notes
                )
                update_ticket(sel_id, updates)
                st.success(f"✅ Ticket #{sel_id} updated.")
                st.rerun()

            if delete_btn:
                delete_ticket(sel_id)
                st.success(f"🗑️ Ticket #{sel_id} deleted.")
                st.rerun()

# ---------------- Main ----------------
def main():
    st.set_page_config(page_title="Tickets Tracker", layout="wide")
    st.title("🎟️ Tickets Tracker (Access-style)")
    init_db()

    tab1, tab2 = st.tabs(["📊 Dashboard", "📝 Add / Edit"])
    with tab1: dashboard()
    with tab2: add_or_edit()

if __name__ == "__main__":
    main()
