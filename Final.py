
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import threading
import time
import platform
from datetime import datetime


# ─────────────────────────────────────────────
#  PLATFORM BEEP
# ─────────────────────────────────────────────
if platform.system() == "Windows":
    import winsound


def play_beep():
    if platform.system() == "Windows":
        winsound.Beep(1000, 600)
    else:
        print("\a")


# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────
DB_PATH = "workflow_tasks.db"

COLORS = {
    "bg"       : "#0D0F18",
    "sidebar"  : "#13162B",
    "card"     : "#1C2040",
    "input"    : "#232749",
    "border"   : "#2E3460",
    "accent"   : "#5C6BC0",
    "accent_h" : "#7986CB",
    "green"    : "#26A69A",
    "orange"   : "#FFA726",
    "red"      : "#EF5350",
    "text"     : "#E8EAF6",
    "muted"    : "#7986CB",
    "white"    : "#FFFFFF",
}

FONTS = {
    "title"  : ("Consolas",  16, "bold"),
    "heading": ("Consolas",  12, "bold"),
    "body"   : ("Consolas",  10),
    "small"  : ("Consolas",   9),
    "big"    : ("Consolas",  26, "bold"),
}

PRIORITY_COLOR = {
    "High"  : COLORS["red"],
    "Medium": COLORS["orange"],
    "Low"   : COLORS["green"],
}

STATUS_COLOR = {
    "Pending": COLORS["orange"],
    "Done"   : COLORS["green"],
}


# ─────────────────────────────────────────────
#  DATABASE HELPERS
# ─────────────────────────────────────────────
def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def db_init():
    with db_connect() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT NOT NULL,
                desc     TEXT DEFAULT '',
                category TEXT DEFAULT 'General',
                due_time TEXT NOT NULL,
                priority TEXT DEFAULT 'Medium',
                status   TEXT DEFAULT 'Pending',
                created  TEXT NOT NULL
            )
        """)
        c.commit()


def db_insert(name, desc, category, due_time, priority):
    with db_connect() as c:
        c.execute(
            """INSERT INTO tasks
               (name, desc, category, due_time, priority, status, created)
               VALUES (?, ?, ?, ?, ?, 'Pending', ?)""",
            (name, desc, category, due_time, priority,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        c.commit()


def db_fetch_all(status_filter="All"):
    with db_connect() as c:
        if status_filter == "All":
            return c.execute(
                "SELECT * FROM tasks ORDER BY due_time ASC"
            ).fetchall()
        return c.execute(
            "SELECT * FROM tasks WHERE status=? ORDER BY due_time ASC",
            (status_filter,)
        ).fetchall()


def db_fetch_one(task_id):
    with db_connect() as c:
        return c.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)
        ).fetchone()


def db_mark_done(task_id):
    with db_connect() as c:
        c.execute("UPDATE tasks SET status='Done' WHERE id=?", (task_id,))
        c.commit()


def db_delete(task_id):
    with db_connect() as c:
        c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        c.commit()


def db_due_pending():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_connect() as c:
        return c.execute(
            "SELECT * FROM tasks WHERE status='Pending' AND due_time <= ?",
            (now,)
        ).fetchall()


def db_counts():
    with db_connect() as c:
        total   = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        pending = c.execute("SELECT COUNT(*) FROM tasks WHERE status='Pending'").fetchone()[0]
        done    = c.execute("SELECT COUNT(*) FROM tasks WHERE status='Done'").fetchone()[0]
    return total, pending, done


def parse_due_time(raw):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M:%S %p"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


# ─────────────────────────────────────────────
#  ADD TASK WINDOW
# ─────────────────────────────────────────────
class AddTaskWindow(tk.Toplevel):

    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.on_save = on_save_callback
        self.title("Add New Task")
        self.geometry("500x540")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.grab_set()
        self._build()

    def _build(self):
        # ── Title bar
        tk.Label(
            self, text="NEW TASK",
            font=FONTS["title"], fg=COLORS["accent_h"], bg=COLORS["bg"]
        ).pack(pady=(22, 6))

        divider = tk.Frame(self, bg=COLORS["border"], height=1)
        divider.pack(fill="x", padx=30, pady=(0, 16))

        # ── Form frame
        form = tk.Frame(self, bg=COLORS["bg"])
        form.pack(fill="x", padx=36)

        def label(text):
            tk.Label(
                form, text=text,
                font=FONTS["small"], fg=COLORS["muted"], bg=COLORS["bg"], anchor="w"
            ).pack(fill="x", pady=(10, 2))

        entry_cfg = dict(
            bg=COLORS["input"], fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat", font=FONTS["body"],
            bd=10
        )

        label("TASK NAME  *")
        self.ent_name = tk.Entry(form, **entry_cfg)
        self.ent_name.pack(fill="x")

        label("DESCRIPTION")
        self.ent_desc = tk.Entry(form, **entry_cfg)
        self.ent_desc.pack(fill="x")

        label("CATEGORY")
        self.var_cat = tk.StringVar(value="General")
        ttk.Combobox(
            form, textvariable=self.var_cat, state="readonly",
            font=FONTS["body"],
            values=["General", "Work", "Personal", "Study", "Health", "Finance"]
        ).pack(fill="x")

        label("DUE DATE & TIME  *   (YYYY-MM-DD HH:MM:SS  or  ... AM/PM)")
        self.ent_due = tk.Entry(form, **entry_cfg)
        self.ent_due.pack(fill="x")

        label("PRIORITY")
        self.var_pri = tk.StringVar(value="Medium")
        pri_row = tk.Frame(form, bg=COLORS["bg"])
        pri_row.pack(fill="x", pady=(2, 0))
        for p, col in [("High", COLORS["red"]), ("Medium", COLORS["orange"]), ("Low", COLORS["green"])]:
            tk.Radiobutton(
                pri_row, text=p, variable=self.var_pri, value=p,
                font=FONTS["body"], fg=col, bg=COLORS["bg"],
                selectcolor=COLORS["input"],
                activebackground=COLORS["bg"], activeforeground=col
            ).pack(side="left", padx=(0, 16))

        # ── Buttons
        btn_row = tk.Frame(self, bg=COLORS["bg"])
        btn_row.pack(pady=24)

        tk.Button(
            btn_row, text="  SAVE TASK  ", command=self._save,
            font=FONTS["body"], bg=COLORS["accent"], fg=COLORS["white"],
            relief="flat", padx=14, pady=9, cursor="hand2",
            activebackground=COLORS["accent_h"], activeforeground=COLORS["white"]
        ).pack(side="left", padx=8)

        tk.Button(
            btn_row, text="  CANCEL  ", command=self.destroy,
            font=FONTS["body"], bg=COLORS["border"], fg=COLORS["text"],
            relief="flat", padx=14, pady=9, cursor="hand2",
            activebackground=COLORS["card"], activeforeground=COLORS["text"]
        ).pack(side="left", padx=8)

    def _save(self):
        name = self.ent_name.get().strip()
        due  = self.ent_due.get().strip()

        if not name:
            messagebox.showerror("Missing Field", "Task name is required.", parent=self)
            return

        parsed = parse_due_time(due)
        if not parsed:
            messagebox.showerror(
                "Invalid Date",
                "Use format:\n  YYYY-MM-DD HH:MM:SS\n  YYYY-MM-DD HH:MM:SS AM/PM",
                parent=self
            )
            return

        db_insert(
            name,
            self.ent_desc.get().strip(),
            self.var_cat.get(),
            parsed,
            self.var_pri.get()
        )
        self.on_save()
        self.destroy()
        messagebox.showinfo("Saved", f"Task '{name}' added successfully!")


# ─────────────────────────────────────────────
#  DETAIL WINDOW
# ─────────────────────────────────────────────
class DetailWindow(tk.Toplevel):

    def __init__(self, parent, task_id):
        super().__init__(parent)
        row = db_fetch_one(task_id)
        if not row:
            self.destroy()
            return
        self.title(f"Task #{row['id']}")
        self.geometry("420x380")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.grab_set()
        self._build(row)

    def _build(self, row):
        tk.Label(
            self, text=row["name"],
            font=FONTS["heading"], fg=COLORS["accent_h"], bg=COLORS["bg"],
            wraplength=360
        ).pack(pady=(22, 8))

        card = tk.Frame(self, bg=COLORS["card"], padx=22, pady=18)
        card.pack(fill="x", padx=24)

        def info_row(key, val, val_color=COLORS["text"]):
            row_f = tk.Frame(card, bg=COLORS["card"])
            row_f.pack(fill="x", pady=3)
            tk.Label(
                row_f, text=f"{key}:", width=11, anchor="w",
                font=FONTS["small"], fg=COLORS["muted"], bg=COLORS["card"]
            ).pack(side="left")
            tk.Label(
                row_f, text=val, anchor="w",
                font=FONTS["body"], fg=val_color, bg=COLORS["card"]
            ).pack(side="left")

        info_row("ID",       f"#{row['id']}")
        info_row("Category", row["category"])
        info_row("Due",      row["due_time"])
        info_row("Priority", row["priority"], PRIORITY_COLOR.get(row["priority"], COLORS["text"]))
        info_row("Status",   row["status"],   STATUS_COLOR.get(row["status"],   COLORS["text"]))
        info_row("Created",  row["created"])

        if row["desc"]:
            tk.Label(
                card, text="Description:", font=FONTS["small"],
                fg=COLORS["muted"], bg=COLORS["card"], anchor="w"
            ).pack(fill="x", pady=(10, 2))
            tk.Label(
                card, text=row["desc"], font=FONTS["body"],
                fg=COLORS["text"], bg=COLORS["card"],
                wraplength=340, justify="left", anchor="w"
            ).pack(fill="x")

        tk.Button(
            self, text="  CLOSE  ", command=self.destroy,
            font=FONTS["body"], bg=COLORS["border"], fg=COLORS["text"],
            relief="flat", padx=14, pady=8, cursor="hand2"
        ).pack(pady=18)


# ─────────────────────────────────────────────
#  REMINDER POPUP
# ─────────────────────────────────────────────
class ReminderPopup(tk.Toplevel):

    def __init__(self, parent, task_name):
        super().__init__(parent)
        self.title("REMINDER")
        self.geometry("380x210")
        self.resizable(False, False)
        self.configure(bg=COLORS["red"])
        self.attributes("-topmost", True)
        self.grab_set()
        self._build(task_name)

    def _build(self, name):
        tk.Label(
            self, text="⏰ TASK DUE NOW!",
            font=FONTS["title"], fg=COLORS["white"], bg=COLORS["red"]
        ).pack(pady=(30, 8))

        tk.Label(
            self, text=name,
            font=FONTS["heading"], fg=COLORS["white"],
            bg=COLORS["red"], wraplength=330
        ).pack(pady=4)

        tk.Label(
            self, text="Marked as Done automatically.",
            font=FONTS["small"], fg="#FFCDD2", bg=COLORS["red"]
        ).pack(pady=4)

        tk.Button(
            self, text="   DISMISS   ", command=self.destroy,
            font=FONTS["body"], bg=COLORS["white"], fg=COLORS["red"],
            relief="flat", padx=12, pady=8, cursor="hand2"
        ).pack(pady=16)


# ─────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────
class App(tk.Tk):

    def __init__(self):
        super().__init__()

        # ── Init database
        db_init()

        # ── Window setup
        self.title("Workflow Automation & Reminder System")
        self.geometry("1150x730")
        self.minsize(900, 600)
        self.configure(bg=COLORS["bg"])

        # ── State
        self._filter    = tk.StringVar(value="All")
        self._alerted   = set()
        self._stat_vars = {}

        # ── Build UI
        self._make_sidebar()
        self._make_main()

        # ── Populate
        self._reload_table()
        self._update_stats()

        # ── Live clock
        self._tick()

        # ── Background reminder thread
        threading.Thread(target=self._reminder_loop, daemon=True).start()

    # ════════════════════════════════════════════
    #  SIDEBAR
    # ════════════════════════════════════════════
    def _make_sidebar(self):
        sb = tk.Frame(self, bg=COLORS["sidebar"], width=240)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        # Logo
        tk.Label(
            sb, text="WORKFLOW",
            font=FONTS["title"], fg=COLORS["accent_h"], bg=COLORS["sidebar"]
        ).pack(pady=(36, 2))

        tk.Label(
            sb, text="automation + reminders",
            font=FONTS["small"], fg=COLORS["muted"], bg=COLORS["sidebar"]
        ).pack(pady=(0, 24))

        tk.Frame(sb, bg=COLORS["border"], height=1).pack(fill="x", padx=20)

        # Filter
        tk.Label(
            sb, text="VIEW",
            font=FONTS["small"], fg=COLORS["muted"], bg=COLORS["sidebar"]
        ).pack(anchor="w", padx=24, pady=(20, 6))

        for opt in ["All", "Pending", "Done"]:
            tk.Radiobutton(
                sb, text=opt, variable=self._filter, value=opt,
                command=self._reload_table,
                font=FONTS["body"], fg=COLORS["text"], bg=COLORS["sidebar"],
                selectcolor=COLORS["accent"],
                activebackground=COLORS["sidebar"], activeforeground=COLORS["accent_h"],
                cursor="hand2"
            ).pack(anchor="w", padx=30, pady=3)

        tk.Frame(sb, bg=COLORS["border"], height=1).pack(fill="x", padx=20, pady=20)

        # Action buttons
        actions = [
            ("+ ADD TASK",    self._open_add,    COLORS["accent"]),
            ("✓ MARK DONE",   self._do_mark,     COLORS["green"]),
            ("✕ DELETE",      self._do_delete,   COLORS["red"]),
            ("↺ REFRESH",     self._reload_table, COLORS["muted"]),
        ]
        for label, cmd, color in actions:
            tk.Button(
                sb, text=label, command=cmd,
                font=FONTS["body"], fg=COLORS["white"], bg=color,
                relief="flat", bd=0, padx=10, pady=10, cursor="hand2",
                activebackground=color, activeforeground=COLORS["white"]
            ).pack(fill="x", padx=22, pady=5)

        # Footer
        tk.Label(
            sb, text="SQLite3  ·  Tkinter",
            font=FONTS["small"], fg=COLORS["border"], bg=COLORS["sidebar"]
        ).pack(side="bottom", pady=16)

    # ════════════════════════════════════════════
    #  MAIN PANEL
    # ════════════════════════════════════════════
    def _make_main(self):
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(side="left", fill="both", expand=True)

        self._make_topbar(main)
        self._make_stat_cards(main)
        self._make_table(main)

    # ── Top bar ───────────────────────────────
    def _make_topbar(self, parent):
        bar = tk.Frame(parent, bg=COLORS["sidebar"], height=62)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(
            bar, text="TASK DASHBOARD",
            font=FONTS["title"], fg=COLORS["text"], bg=COLORS["sidebar"]
        ).pack(side="left", padx=24, pady=14)

        self._clock_lbl = tk.Label(
            bar, text="",
            font=FONTS["small"], fg=COLORS["muted"], bg=COLORS["sidebar"]
        )
        self._clock_lbl.pack(side="right", padx=24)

    # ── Stat cards ────────────────────────────
    def _make_stat_cards(self, parent):
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill="x", padx=20, pady=(16, 0))

        specs = [
            ("total",   "TOTAL",     COLORS["accent_h"]),
            ("pending", "PENDING",   COLORS["orange"]),
            ("done",    "COMPLETED", COLORS["green"]),
        ]

        for key, label, color in specs:
            card = tk.Frame(row, bg=COLORS["card"], padx=22, pady=14)
            card.pack(side="left", padx=(0, 14))

            tk.Label(
                card, text=label,
                font=FONTS["small"], fg=COLORS["muted"], bg=COLORS["card"]
            ).pack(anchor="w")

            var = tk.StringVar(value="0")
            self._stat_vars[key] = var
            tk.Label(
                card, textvariable=var,
                font=FONTS["big"], fg=color, bg=COLORS["card"]
            ).pack(anchor="w")

    # ── Task table ────────────────────────────
    def _make_table(self, parent):
        wrapper = tk.Frame(parent, bg=COLORS["bg"])
        wrapper.pack(fill="both", expand=True, padx=20, pady=16)

        # Style
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "WF.Treeview",
            background=COLORS["card"],
            fieldbackground=COLORS["card"],
            foreground=COLORS["text"],
            font=("Consolas", 10),
            rowheight=34,
            borderwidth=0
        )
        style.configure(
            "WF.Treeview.Heading",
            background=COLORS["border"],
            foreground=COLORS["muted"],
            font=("Consolas", 9, "bold"),
            relief="flat"
        )
        style.map(
            "WF.Treeview",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", COLORS["white"])]
        )

        cols = ("ID", "Task Name", "Category", "Due Date/Time", "Priority", "Status", "Created")
        widths = (44, 230, 100, 152, 80, 82, 148)

        self._tree = ttk.Treeview(
            wrapper, columns=cols,
            show="headings", style="WF.Treeview",
            selectmode="browse"
        )
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="w" if col == "Task Name" else "center")

        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)

        # Row colour tags
        self._tree.tag_configure("done",    foreground=COLORS["green"])
        self._tree.tag_configure("overdue", foreground=COLORS["red"])
        self._tree.tag_configure("high",    foreground=COLORS["red"])
        self._tree.tag_configure("medium",  foreground=COLORS["orange"])
        self._tree.tag_configure("low",     foreground=COLORS["green"])

        # Bindings
        self._tree.bind("<Double-1>",  lambda _: self._open_detail())
        self._tree.bind("<Button-3>",  self._ctx_menu_show)

        # Context menu
        self._ctx = tk.Menu(
            self, tearoff=0,
            bg=COLORS["card"], fg=COLORS["text"],
            activebackground=COLORS["accent"],
            activeforeground=COLORS["white"],
            font=FONTS["body"]
        )
        self._ctx.add_command(label="  View Details",  command=self._open_detail)
        self._ctx.add_separator()
        self._ctx.add_command(label="  Mark as Done",  command=self._do_mark)
        self._ctx.add_command(label="  Delete Task",   command=self._do_delete)

    # ════════════════════════════════════════════
    #  TABLE LOGIC
    # ════════════════════════════════════════════
    def _reload_table(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        now = datetime.now()
        tasks = db_fetch_all(self._filter.get())

        for t in tasks:
            try:
                due_dt  = datetime.strptime(t["due_time"], "%Y-%m-%d %H:%M:%S")
                overdue = due_dt < now and t["status"] == "Pending"
            except Exception:
                overdue = False

            if t["status"] == "Done":
                tag = "done"
            elif overdue:
                tag = "overdue"
            else:
                tag = t["priority"].lower()

            self._tree.insert(
                "", "end",
                iid=str(t["id"]),
                tags=(tag,),
                values=(
                    t["id"], t["name"], t["category"],
                    t["due_time"], t["priority"], t["status"], t["created"]
                )
            )

        self._update_stats()

    def _update_stats(self):
        total, pending, done = db_counts()
        self._stat_vars["total"].set(str(total))
        self._stat_vars["pending"].set(str(pending))
        self._stat_vars["done"].set(str(done))

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Nothing Selected", "Please click a task row first.")
            return None
        return int(sel[0])

    def _ctx_menu_show(self, event):
        row = self._tree.identify_row(event.y)
        if row:
            self._tree.selection_set(row)
            self._ctx.tk_popup(event.x_root, event.y_root)

    # ════════════════════════════════════════════
    #  ACTIONS
    # ════════════════════════════════════════════
    def _open_add(self):
        AddTaskWindow(self, on_save_callback=self._reload_table)

    def _open_detail(self):
        tid = self._selected_id()
        if tid:
            DetailWindow(self, tid)

    def _do_mark(self):
        tid = self._selected_id()
        if tid:
            db_mark_done(tid)
            self._reload_table()

    def _do_delete(self):
        tid = self._selected_id()
        if tid:
            if messagebox.askyesno("Confirm Delete", "Permanently delete this task?"):
                db_delete(tid)
                self._reload_table()

    # ════════════════════════════════════════════
    #  CLOCK
    # ════════════════════════════════════════════
    def _tick(self):
        now = datetime.now().strftime("%a  %d %b %Y   %H:%M:%S")
        self._clock_lbl.config(text=now)
        self.after(1000, self._tick)

    # ════════════════════════════════════════════
    #  REMINDER BACKGROUND THREAD
    # ════════════════════════════════════════════
    def _reminder_loop(self):
        while True:
            for task in db_due_pending():
                tid = task["id"]
                if tid not in self._alerted:
                    self._alerted.add(tid)
                    db_mark_done(tid)
                    name = task["name"]
                    self.after(0, lambda n=name: self._fire_reminder(n))
            time.sleep(10)

    def _fire_reminder(self, name):
        play_beep()
        self._reload_table()
        ReminderPopup(self, name)


# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
