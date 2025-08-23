# app.py
import datetime as dt
from datetime import date
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

DB_PATH = Path("tickets.db")

USERS = ["Flora", "Diana", "Vinny", "Sam", "Geetiak", "Dharminder"]
COMMUNICATION = ["Informed Customer", "Waiting for Customer Response", "On Hold as per Customer"]

# ✅ Updated priorities to match spec
PRIORITY = ["Today", "Today 2", "Tomorrow", "2 days"]

PRIORITY_COLORS = {
    "Today": "#ff9999",       # Light Red
    "Today 2": "#ffff66",     # Yellow
    "Tomorrow": "#66b3ff",    # Blue
    "2 days": "#bfbfbf",      # Grey
}
STATUS = ["Not Started", "In Progress", "Blocked", "Completed"]

STATUS_COLORS = {
    "Not Started": "#c00000",
    "In Progress": "#ed7d31",
    "Blocked": "#7030a0",
    "Completed": "#00b050",
}

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
                attention_owner TEXT,
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
                date_entered, time_entered, communication, entered_by, attention_owner,
                fba_customer, instructions_order_id, priority, due_date, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["date_entered"],
            row["time_entered"],
            row["communication"],
            row["entered_by"],
            row["attention_owner"],
            row["fba_customer"],
            row["instructions_order_id"],
            row["priority"],
            row["due_date"],
            row["status"],
            row["notes"]
        ))
        con.commit()
        return cur.lastrowid

def update_ticket(ticket_id: int, updates: dict):
    cols = []
    vals = []
    for k, v in updates.items():
        cols.append(f"{k}=?")
        vals.append(v)
    vals.append(ticket_id)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(f"UPDATE tickets SET {', '.join(cols)} WHERE id= ?", vals)
        con.commit()

def load_tickets(where_clause="", params=()):
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(f"SELECT * FROM tickets {where_clause} ORDER BY id DESC", con, params=params)
    return df

def color_badge(text: str, color_map: dict) -> str:
    color = color_map.get(text, "#444")
    fg = "#000"
    return f"""<span style="
        background:{color};
        color:{fg};
        padding:2px 8px;
        border-radius:999px;
        font-size:0.85rem;
        white-space:nowrap;
        ">{text}</span>"""

def render_table(df: pd.DataFrame):
    if df.empty:
        st.info("No tickets yet.")
        return
    df = df.copy()
    df["Priority"] = df["priority"].apply(lambda t: color_badge(t, PRIORITY_COLORS))
    df["Status"] = df["status"].apply(lambda t: color_badge(t, STATUS_COLORS))
    df.rename(columns={
        "id": "ID",
        "date_entered": "Date Entered",
        "time_entered": "Time Entered",
        "communication": "Communication",
        "entered_by": "Entered By",
        "attention_owner": "Attention Owner",
        "fba_customer": "FBA Customer",
        "instructions_order_id": "Instructions/Order ID",
        "due_date": "Due Date",
        "notes": "Notes",
    }, inplace=True)
    columns = ["ID","Date Entered","Time Entered","Communication","Entered By","Attention Owner",
               "FBA Customer","Instructions/Order ID","Priority","Due Date","Status","Notes"]
    df = df[columns]

    # ✅ Custom CSS for alignment and wrapping
    st.markdown("""
    <style>
    table.dataframe th, table.dataframe td {
        text-align: center !important;
        vertical-align: middle !important;
    }
    table.dataframe td:nth-child(8) { /* Instructions/Order ID */
        min-width: 250px;
        white-space: normal !important;
        word-wrap: break-word !important;
    }
    table.dataframe td:nth-child(12) { /* Notes */
        white-space: normal !important;
        word-wrap: break-word !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)

def dashboard():
    st.subheader("Dashboard")
    colA, colB, colC, colD = st.columns([1,1,1,1])
    with colA:
        scope = st.radio("Scope", ["All", "Due Today", "Overdue & Open"], horizontal=True)
    with colB:
        f_priority = st.selectbox("Priority", ["(Any)"] + PRIORITY)
    with colC:
        f_status = st.selectbox("Status", ["(Any)"] + STATUS)
    with colD:
        search = st.text_input("Search (Customer / Order / Notes)")

    where = []
    params = []

    if scope == "Due Today":
        where.append("due_date = ?")
        params.append(date.today().isoformat())
    elif scope == "Overdue & Open":
        where.append("due_date < ?")
        params.append(date.today().isoformat())
        where.append("status IN ('Not Started','In Progress','Blocked')")

    if f_priority != "(Any)":
        where.append("priority = ?")
        params.append(f_priority)
    if f_status != "(Any)":
        where.append("status = ?")
        params.append(f_status)
    if search:
        where.append("(LOWER(fba_customer) LIKE ? OR LOWER(instructions_order_id) LIKE ? OR LOWER(notes) LIKE ?)")
        like = f"%{search.lower()}%"
        params.extend([like, like, like])

    clause = "WHERE " + " AND ".join(where) if where else ""
    df = load_tickets(clause, tuple(params))

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("Refresh"):
            df = load_tickets(clause, tuple(params))
    with c2:
        if not df.empty:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Export CSV", csv, "tickets_export.csv", "text/csv")
    with c3:
        st.write("")

    render_table(df)

def add_or_edit():
    st.subheader("Add / Edit Tickets")

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
        now = dt.datetime.now()
        row = {
            "date_entered": date.today().isoformat(),
            "time_entered": now.strftime("%I:%M %p"),   # ✅ AM/PM
            "communication": COMMUNICATION[0],
            "entered_by": "Diana",
            "attention_owner": USERS[0],
            "fba_customer": "",
            "instructions_order_id": "",
            "priority": PRIORITY[0],
            "due_date": date.today().isoformat(),
            "status": STATUS[0],
            "notes": "",
        }

    with st.form("ticket_form", clear_on_submit=False):
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            st.text_input("Date Entered (auto)", value=row["date_entered"], disabled=True)
        with c2:
            st.text_input("Time Entered (auto)", value=row["time_entered"], disabled=True)
        with c3:
            due = st.date_input("Due Date", value=dt.date.fromisoformat(row["due_date"]))

        c4, c5, c6 = st.columns([1,1,1])
        with c4:
            comm = st.selectbox("Communication", COMMUNICATION, index=COMMUNICATION.index(row["communication"]) if row["communication"] in COMMUNICATION else 0)
        with c5:
            ent = st.selectbox("Entered By", USERS, index=USERS.index(row["entered_by"]) if row["entered_by"] in USERS else USERS.index("Diana"))
        with c6:
            own = st.selectbox("Attention Owner", USERS, index=USERS.index(row["attention_owner"]) if row["attention_owner"] in USERS else 0)

        c7, c8 = st.columns([1,1])
        with c7:
            pr = st.selectbox("Priority", PRIORITY, index=PRIORITY.index(row["priority"]) if row["priority"] in PRIORITY else 0)
        with c8:
            stt = st.selectbox("Status", STATUS, index=STATUS.index(row["status"]) if row["status"] in STATUS else 0)

        # ✅ Auto-set due_date based on priority
        if pr == "Today":
            due = date.today()
        elif pr == "Today 2":
            due = date.today()
        elif pr == "Tomorrow":
            due = date.today() + dt.timedelta(days=1)
        elif pr == "2 days":
            due = date.today() + dt.timedelta(days=2)

        cust = st.text_input("FBA Customer", value=row["fba_customer"])
        instr = st.text_input("Instructions / Order ID", value=row["instructions_order_id"])
        notes = st.text_area("Notes by Owner/Assignee", value=row["notes"], height=120)

        if mode == "Add New":
            submitted = st.form_submit_button("Add Ticket")
            if submitted:
                payload = dict(
                    date_entered=date.today().isoformat(),
                    time_entered=dt.datetime.now().strftime("%I:%M %p"),   # ✅ AM/PM
                    communication=comm,
                    entered_by=ent,
                    attention_owner=own,
                    fba_customer=cust,
                    instructions_order_id=instr,
                    priority=pr,
                    due_date=due.isoformat() if isinstance(due, dt.date) else str(due),
                    status=stt,
                    notes=notes
                )
                new_id = insert_ticket(payload)
                st.success(f"Ticket #{new_id} added.")
        else:
            submitted = st.form_submit_button("Save Changes")
            if submitted:
                updates = dict(
                    communication=comm,
                    entered_by=ent,
                    attention_owner=own,
                    fba_customer=cust,
                    instructions_order_id=instr,
                    priority=pr,
                    due_date=due.isoformat() if isinstance(due, dt.date) else str(due),
                    status=stt,
                    notes=notes
                )
                update_ticket(sel_id, updates)
                st.success(f"Ticket #{sel_id} updated.")

def main():
    st.set_page_config(page_title="Tickets Tracker", layout="wide")
    st.title("Tickets Tracker (Access-style)")
    init_db()

    tab1, tab2 = st.tabs(["📊 Dashboard", "📝 Add / Edit"])
    with tab1:
        dashboard()
    with tab2:
        add_or_edit()

if __name__ == "__main__":
    main()
