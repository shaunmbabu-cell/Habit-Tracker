"""
Ritual — Advanced Habit Tracker
New features added:
  • Reminders / due-time per habit with visual urgency indicator
  • Pomodoro-style focus timer (any habit)
  • Habit categories / tags for grouping
  • Pause / archive habit (skip without breaking streak)
  • Quick-log past missed days (backfill, up to 3 days)
  • Daily challenge: random habit suggestion
  • Export data to CSV
  • Import / restore from JSON backup
  • Settings page: user name, week-start day, streak-grace toggle
  • Streak-grace: one missed day per week doesn't reset streak
  • Completion sound toggle (system bell)
  • Search / filter habits
  • Undo last toggle (per session)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json, os, csv, threading, time, random
from datetime import datetime, timedelta, date

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "habits.json")

# ─── PALETTE ──────────────────────────────────────────────────────────────────
C = dict(
    bg       = "#0d0d14", surface  = "#13131f", card     = "#1a1a2e",
    card2    = "#1f1f35", border   = "#2a2a45", border2  = "#353560",
    violet   = "#7b61ff", violet2  = "#a78bfa", violet3  = "#c4b5fd",
    mint     = "#34d399", mint2    = "#6ee7b7", coral    = "#fb7185",
    amber    = "#fbbf24", sky      = "#38bdf8", pink     = "#f472b6",
    text     = "#f0eeff", sub      = "#8b8bae", dim      = "#4a4a7a",
    white    = "#ffffff",
)

TINTS = {
    "#7b61ff":"#1e1a3a","#a78bfa":"#1e1a3a","#c4b5fd":"#1e1a3a",
    "#34d399":"#0d2e22","#6ee7b7":"#0d2e22","#fb7185":"#2e0d15",
    "#fbbf24":"#2e2008","#38bdf8":"#0d1e2e","#f472b6":"#2e0d22",
    "#a3e635":"#1a2e0d",
}

ACCENT_COLORS = ["#7b61ff","#34d399","#fb7185","#fbbf24","#38bdf8","#f472b6","#a3e635"]
CATEGORIES    = ["Health","Fitness","Learning","Mindfulness","Productivity",
                 "Social","Finance","Creative","Other"]

F = {}
def setup_fonts():
    F['title'] = ("Georgia",26,"bold");   F['h1']    = ("Georgia",18,"bold")
    F['h2']    = ("Georgia",14,"bold");   F['h3']    = ("Georgia",11,"bold italic")
    F['body']  = ("Courier New",10);      F['label'] = ("Courier New",9)
    F['small'] = ("Courier New",8);       F['mono']  = ("Courier New",11,"bold")
    F['big']   = ("Georgia",32,"bold");   F['huge']  = ("Georgia",48,"bold")

# ─── DATA ─────────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "username":"Friend","streak_grace":False,"sound":True,"show_archived":False,
}

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("habits",{}); d.setdefault("journal",{})
        d.setdefault("settings", DEFAULT_SETTINGS.copy())
        return d
    return {"habits":{},"journal":{},"settings":DEFAULT_SETTINGS.copy()}

def save(data):
    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def today_str(): return date.today().isoformat()

def streak(dates, grace=False):
    if not dates: return 0
    s = sorted(set(dates), reverse=True)
    count, check, misses = 0, date.today(), 0
    for ds in s:
        d = date.fromisoformat(ds)
        while d < check:
            if grace and misses == 0: misses += 1; check -= timedelta(1)
            else: return count
        if d == check: count += 1; check -= timedelta(1)
    return count

def completion_rate(dates, n_days):
    end = date.today()
    window = {(end-timedelta(i)).isoformat() for i in range(n_days)}
    return len(set(dates) & window)/n_days if n_days else 0

def last_n_days(n):
    today = date.today()
    return [(today-timedelta(i)).isoformat() for i in range(n-1,-1,-1)]

def time_greeting():
    h = datetime.now().hour
    return "Good morning" if h<12 else "Good afternoon" if h<17 else "Good evening"

# ─── BASE WIDGETS ─────────────────────────────────────────────────────────────
class Tooltip:
    def __init__(self, widget, text):
        self.widget=widget; self.text=text; self.tip=None
        widget.bind("<Enter>",self.show); widget.bind("<Leave>",self.hide)
    def show(self, e=None):
        x=self.widget.winfo_rootx()+20; y=self.widget.winfo_rooty()+self.widget.winfo_height()+4
        self.tip=tk.Toplevel(self.widget); self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip,text=self.text,font=F['small'],bg=C['border2'],fg=C['text'],padx=8,pady=4).pack()
    def hide(self,e=None):
        if self.tip: self.tip.destroy(); self.tip=None

class ScrollFrame(tk.Frame):
    def __init__(self, parent, **kw):
        bg=kw.get('bg',C['bg'])
        super().__init__(parent,bg=bg)
        self.canvas=tk.Canvas(self,bg=bg,highlightthickness=0,bd=0)
        sb=tk.Scrollbar(self,orient="vertical",command=self.canvas.yview,
                        bg=C['border'],troughcolor=C['surface'])
        self.inner=tk.Frame(self.canvas,bg=bg)
        self.win=self.canvas.create_window((0,0),window=self.inner,anchor="nw")
        self.inner.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",lambda e:self.canvas.itemconfig(self.win,width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right",fill="y"); self.canvas.pack(side="left",fill="both",expand=True)
        self.canvas.bind_all("<MouseWheel>",self._scroll)
    def _scroll(self,e): self.canvas.yview_scroll(int(-1*(e.delta/120)),"units")

def btn(parent, text, cmd, bg=None, fg=None, font=None, pad=(14,7), **kw):
    return tk.Button(parent,text=text,command=cmd,bg=bg or C['violet'],fg=fg or C['white'],
                     font=font or F['label'],relief="flat",bd=0,cursor="hand2",
                     activebackground=C['violet2'],activeforeground=C['white'],
                     padx=pad[0],pady=pad[1],**kw)

def tag(parent, text, color):
    bg=TINTS.get(color,"#1e1e30")
    f=tk.Frame(parent,bg=bg,padx=8,pady=2)
    tk.Label(f,text=text,font=F['small'],bg=bg,fg=color).pack()
    return f

def divider(parent, color=None):
    tk.Frame(parent,bg=color or C['border'],height=1).pack(fill="x",pady=8)

def section_header(parent, title):
    f=tk.Frame(parent,bg=C['bg']); f.pack(fill="x",pady=(14,4))
    tk.Label(f,text=title,font=F['small'],bg=C['bg'],fg=C['sub']).pack(side="left")
    tk.Frame(f,bg=C['border'],height=1).pack(side="left",fill="x",expand=True,padx=10,pady=8)

# ─── HABIT DIALOG ─────────────────────────────────────────────────────────────
class HabitDialog(tk.Toplevel):
    def __init__(self, parent, title="New Habit", habit=None):
        super().__init__(parent)
        self.title(title); self.configure(bg=C['surface'])
        self.resizable(False,False); self.result=None
        if not F: setup_fonts()
        w,h=500,620; self.geometry(f"{w}x{h}"); self.update_idletasks()
        px,py,pw,ph=(parent.winfo_rootx(),parent.winfo_rooty(),
                     parent.winfo_width(),parent.winfo_height())
        if pw>1 and ph>1: self.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")
        self.grab_set()

        sf=ScrollFrame(self,bg=C['surface']); sf.pack(fill="both",expand=True)
        body=sf.inner

        tk.Label(body,text=title,font=F['h1'],bg=C['surface'],fg=C['text']
                 ).pack(pady=(24,4),padx=28,anchor="w")
        tk.Frame(body,bg=C['violet'],height=2).pack(fill="x",padx=28,pady=(0,16))

        def lbl(t): tk.Label(body,text=t,font=F['small'],bg=C['surface'],fg=C['sub']).pack(anchor="w",padx=28)
        def entry_w(**kw): return tk.Entry(body,font=F['body'],bg=C['card'],fg=C['text'],
                                            insertbackground=C['text'],relief="flat",
                                            highlightbackground=C['border'],highlightthickness=1,**kw)

        lbl("HABIT NAME")
        self.name_var=tk.StringVar(value=habit['name'] if habit else "")
        e=entry_w(textvariable=self.name_var); e.pack(fill="x",padx=28,pady=(4,12),ipady=8); e.focus()

        lbl("CATEGORY")
        self.cat_var=tk.StringVar(value=habit.get('category','Other') if habit else "Other")
        cf2=tk.Frame(body,bg=C['surface']); cf2.pack(fill="x",padx=28,pady=(4,12))
        ttk.Combobox(cf2,textvariable=self.cat_var,values=CATEGORIES,
                     state="readonly",font=F['body']).pack(fill="x",ipady=4)

        lbl("TYPE")
        self.type_var=tk.StringVar(value=habit['type'] if habit else "build")
        tf=tk.Frame(body,bg=C['surface']); tf.pack(fill="x",padx=28,pady=(4,12))
        for val,lb,col in [("build","✦ Build","#34d399"),("break","✗ Break","#fb7185")]:
            tk.Radiobutton(tf,text=lb,variable=self.type_var,value=val,font=F['label'],
                           bg=C['surface'],fg=col,selectcolor=C['card'],
                           activebackground=C['surface'],activeforeground=col
                           ).pack(side="left",padx=(0,16))

        lbl("FREQUENCY")
        self.freq_var=tk.StringVar(value=habit['freq'] if habit else "daily")
        ff=tk.Frame(body,bg=C['surface']); ff.pack(fill="x",padx=28,pady=(4,12))
        for val,lb in [("daily","Daily"),("weekly","Weekly"),("monthly","Monthly")]:
            tk.Radiobutton(ff,text=lb,variable=self.freq_var,value=val,font=F['label'],
                           bg=C['surface'],fg=C['text'],selectcolor=C['card'],
                           activebackground=C['surface']).pack(side="left",padx=(0,12))

        lbl("TARGET (times per period)")
        self.target_var=tk.StringVar(value=str(habit.get('target',1)) if habit else "1")
        entry_w(textvariable=self.target_var,width=6).pack(anchor="w",padx=28,pady=(4,12),ipady=6)

        lbl("REMINDER TIME (HH:MM, optional)")
        self.remind_var=tk.StringVar(value=habit.get('remind','') if habit else "")
        entry_w(textvariable=self.remind_var,width=10).pack(anchor="w",padx=28,pady=(4,12),ipady=6)

        lbl("GOAL / MOTIVATION (optional)")
        self.goal_var=tk.StringVar(value=habit.get('goal','') if habit else "")
        entry_w(textvariable=self.goal_var).pack(fill="x",padx=28,pady=(4,12),ipady=8)

        lbl("EMOJI / ICON")
        self.emoji_var=tk.StringVar(value=habit.get('emoji','') if habit else "")
        entry_w(textvariable=self.emoji_var,width=6).pack(anchor="w",padx=28,pady=(4,12),ipady=6)

        lbl("COLOR ACCENT")
        self.color_var=tk.StringVar(value=habit.get('color','#7b61ff') if habit else "#7b61ff")
        clf=tk.Frame(body,bg=C['surface']); clf.pack(anchor="w",padx=28,pady=(4,16))
        for c in ACCENT_COLORS:
            tk.Radiobutton(clf,variable=self.color_var,value=c,bg=c,activebackground=c,
                           selectcolor=c,indicatoron=False,width=2,height=1,
                           relief="flat",cursor="hand2").pack(side="left",padx=3)

        bf=tk.Frame(body,bg=C['surface']); bf.pack(fill="x",padx=28,pady=(8,24))
        btn(bf,"Cancel",self.destroy,bg=C['card'],fg=C['sub']).pack(side="left")
        btn(bf,"Save Habit",self._save).pack(side="right")

    def _save(self):
        name=self.name_var.get().strip()
        if not name: messagebox.showerror("Error","Please enter a habit name.",parent=self); return
        try: target=max(1,int(self.target_var.get()))
        except: target=1
        remind=self.remind_var.get().strip()
        if remind:
            try: datetime.strptime(remind,"%H:%M")
            except: messagebox.showerror("Error","Reminder must be HH:MM.",parent=self); return
        self.result=dict(name=name,type=self.type_var.get(),freq=self.freq_var.get(),
                         goal=self.goal_var.get().strip(),emoji=self.emoji_var.get().strip(),
                         color=self.color_var.get(),target=target,remind=remind,
                         category=self.cat_var.get())
        self.destroy()

# ─── BACKFILL DIALOG ──────────────────────────────────────────────────────────
class BackfillDialog(tk.Toplevel):
    def __init__(self, parent, habit_name, completions):
        super().__init__(parent)
        self.title("Log Past Days"); self.configure(bg=C['surface'])
        self.resizable(False,False); self.result=None
        if not F: setup_fonts()
        w,h=340,280; self.geometry(f"{w}x{h}"); self.update_idletasks()
        px,py,pw,ph=(parent.winfo_rootx(),parent.winfo_rooty(),
                     parent.winfo_width(),parent.winfo_height())
        if pw>1 and ph>1: self.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")
        self.grab_set()

        tk.Label(self,text="Log Past Days",font=F['h1'],bg=C['surface'],fg=C['text']
                 ).pack(pady=(20,4),padx=24,anchor="w")
        tk.Label(self,text=f"Habit:  {habit_name}",font=F['small'],
                 bg=C['surface'],fg=C['sub']).pack(padx=24,anchor="w")
        tk.Frame(self,bg=C['violet'],height=2).pack(fill="x",padx=24,pady=(8,14))

        self.vars={}
        comp_set=set(completions)
        for i in range(1,4):
            d=(date.today()-timedelta(i)).isoformat()
            label=(date.today()-timedelta(i)).strftime("%A, %b %d")
            var=tk.BooleanVar(value=d in comp_set); self.vars[d]=var
            row=tk.Frame(self,bg=C['surface']); row.pack(fill="x",padx=24,pady=3)
            tk.Checkbutton(row,text=label,variable=var,font=F['body'],
                           bg=C['surface'],fg=C['text'],selectcolor=C['card'],
                           activebackground=C['surface']).pack(side="left")

        bf=tk.Frame(self,bg=C['surface']); bf.pack(fill="x",padx=24,pady=16)
        btn(bf,"Cancel",self.destroy,bg=C['card'],fg=C['sub']).pack(side="left")
        btn(bf,"Save",self._save).pack(side="right")

    def _save(self): self.result={d:v.get() for d,v in self.vars.items()}; self.destroy()

# ─── FOCUS TIMER ──────────────────────────────────────────────────────────────
class FocusTimer(tk.Toplevel):
    def __init__(self, parent, habit_name=""):
        super().__init__(parent)
        self.title("Focus Timer"); self.configure(bg=C['bg'])
        self.resizable(False,False)
        if not F: setup_fonts()
        w,h=360,400; self.geometry(f"{w}x{h}"); self.update_idletasks()
        px,py,pw,ph=(parent.winfo_rootx(),parent.winfo_rooty(),
                     parent.winfo_width(),parent.winfo_height())
        if pw>1 and ph>1: self.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")

        self.habit_name=habit_name; self.total=25*60; self.remaining=self.total
        self.running=False; self._job=None

        tk.Label(self,text="◎  Focus Timer",font=F['h1'],bg=C['bg'],fg=C['text']).pack(pady=(24,2))
        tk.Label(self,text=habit_name,font=F['h3'],bg=C['bg'],fg=C['violet2']).pack()
        tk.Frame(self,bg=C['border'],height=1).pack(fill="x",padx=32,pady=12)

        pf=tk.Frame(self,bg=C['bg']); pf.pack(pady=4)
        for label,secs in [("5 min",300),("15 min",900),("25 min",1500),("50 min",3000)]:
            btn(pf,label,lambda s=secs:self._set(s),bg=C['card'],fg=C['sub'],pad=(9,4)
                ).pack(side="left",padx=3)

        self.disp=tk.StringVar(value="25:00")
        tk.Label(self,textvariable=self.disp,font=F['huge'],bg=C['bg'],fg=C['text']).pack(pady=12)

        self.arc=tk.Canvas(self,width=200,height=18,bg=C['bg'],highlightthickness=0)
        self.arc.pack()
        self.arc.create_rectangle(0,3,200,15,outline=C['border'],fill=C['border'])
        self.bar=self.arc.create_rectangle(0,3,0,15,fill=C['violet'],outline="")

        cf=tk.Frame(self,bg=C['bg']); cf.pack(pady=14)
        self.sbtn=btn(cf,"▶  Start",self._toggle,bg=C['violet'],pad=(18,9)); self.sbtn.pack(side="left",padx=5)
        btn(cf,"↺  Reset",self._reset,bg=C['card'],fg=C['sub'],pad=(12,9)).pack(side="left",padx=5)

        self.status=tk.StringVar(value="Ready")
        tk.Label(self,textvariable=self.status,font=F['small'],bg=C['bg'],fg=C['sub']).pack()
        self.protocol("WM_DELETE_WINDOW",self._close)

    def _set(self,s):
        if self.running: return
        self.total=s; self.remaining=s; self._upd()

    def _toggle(self):
        if self.running:
            self.running=False; self.sbtn.configure(text="▶  Resume"); self.status.set("Paused")
        else:
            self.running=True; self.sbtn.configure(text="⏸  Pause"); self.status.set("Focusing…"); self._tick()

    def _tick(self):
        if not self.running: return
        if self.remaining<=0:
            self.running=False; self.sbtn.configure(text="▶  Start")
            self.status.set("✓ Done!"); self.bell(); return
        self.remaining-=1; self._upd(); self._job=self.after(1000,self._tick)

    def _upd(self):
        m,s=divmod(self.remaining,60); self.disp.set(f"{m:02d}:{s:02d}")
        frac=(self.total-self.remaining)/self.total if self.total else 0
        self.arc.coords(self.bar,0,3,int(200*frac),15)

    def _reset(self):
        self.running=False
        if self._job: self.after_cancel(self._job)
        self.remaining=self.total; self._upd(); self.sbtn.configure(text="▶  Start"); self.status.set("Ready")

    def _close(self):
        self.running=False
        if self._job: self.after_cancel(self._job)
        self.destroy()

# ─── MAIN APP ─────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        setup_fonts()
        self.title("Ritual — Habit Tracker"); self.geometry("1120x740")
        self.minsize(920,620); self.configure(bg=C['bg'])
        self.data=load(); self._undo_stack=[]; self.active_tab="dashboard"
        self._build(); self._start_reminder_thread(); self.show("dashboard")

    def _build(self):
        self.sidebar=tk.Frame(self,bg=C['surface'],width=220)
        self.sidebar.pack(side="left",fill="y"); self.sidebar.pack_propagate(False)
        lf=tk.Frame(self.sidebar,bg=C['surface']); lf.pack(fill="x",pady=(28,0),padx=24)
        tk.Label(lf,text="◈",font=("Georgia",28,"bold"),bg=C['surface'],fg=C['violet']).pack(side="left")
        tf=tk.Frame(lf,bg=C['surface']); tf.pack(side="left",padx=8)
        tk.Label(tf,text="ritual",font=("Georgia",16,"bold"),bg=C['surface'],fg=C['text']).pack(anchor="w")
        tk.Label(tf,text="habit tracker",font=F['small'],bg=C['surface'],fg=C['dim']).pack(anchor="w")
        tk.Frame(self.sidebar,bg=C['border'],height=1).pack(fill="x",padx=24,pady=20)

        self.nav_btns={}
        for key,label in [("dashboard","◉  Dashboard"),("habits","◈  My Habits"),
                           ("analytics","◎  Analytics"),("journal","◇  Journal"),
                           ("settings","⚙  Settings")]:
            b=tk.Button(self.sidebar,text=label,font=F['label'],bg=C['surface'],fg=C['sub'],
                        relief="flat",bd=0,cursor="hand2",anchor="w",padx=24,pady=11,
                        activebackground=C['card'],activeforeground=C['text'],
                        command=lambda k=key:self.show(k))
            b.pack(fill="x"); self.nav_btns[key]=b

        tk.Frame(self.sidebar,bg=C['border'],height=1).pack(fill="x",padx=24,pady=16,side="bottom")
        tk.Button(self.sidebar,text="↩  Undo Last",font=F['small'],bg=C['surface'],fg=C['dim'],
                  relief="flat",bd=0,cursor="hand2",padx=24,pady=6,command=self._undo,
                  activebackground=C['card'],activeforeground=C['text']
                  ).pack(side="bottom",fill="x")
        tk.Label(self.sidebar,text=date.today().strftime("%a, %b %d"),
                 font=F['small'],bg=C['surface'],fg=C['dim']).pack(side="bottom",pady=(0,4))
        tk.Label(self.sidebar,text="TODAY",font=F['small'],bg=C['surface'],fg=C['sub']).pack(side="bottom")

        self.content=tk.Frame(self,bg=C['bg']); self.content.pack(side="left",fill="both",expand=True)
        self.pages={}
        for Cls,key in [(DashboardPage,"dashboard"),(HabitsPage,"habits"),
                        (AnalyticsPage,"analytics"),(JournalPage,"journal"),(SettingsPage,"settings")]:
            p=Cls(self.content,self)
            p.place(relx=0,rely=0,relwidth=1,relheight=1)
            self.pages[key]=p

    def show(self,key):
        for k,b in self.nav_btns.items():
            if k==key: b.configure(bg=C['card'],fg=C['violet2'],font=("Courier New",9,"bold"))
            else: b.configure(bg=C['surface'],fg=C['sub'],font=F['label'])
        self.pages[key].refresh(); self.pages[key].tkraise(); self.active_tab=key

    def push_undo(self,name,day,added): self._undo_stack.append((name,day,added))

    def _undo(self):
        if not self._undo_stack: messagebox.showinfo("Undo","Nothing to undo.",parent=self); return
        name,day,added=self._undo_stack.pop()
        if name not in self.data["habits"]: messagebox.showinfo("Undo","Habit no longer exists.",parent=self); return
        comps=self.data["habits"][name].setdefault("completions",[])
        if added and day in comps: comps.remove(day)
        elif not added and day not in comps: comps.append(day)
        save(self.data); self.pages[self.active_tab].refresh()

    def grace_on(self): return self.data["settings"].get("streak_grace",False)
    def sound_on(self): return self.data["settings"].get("sound",True)

    def _start_reminder_thread(self):
        self._reminded_today=set()
        threading.Thread(target=self._reminder_loop,daemon=True).start()

    def _reminder_loop(self):
        while True:
            time.sleep(30)
            now=datetime.now().strftime("%H:%M"); today=today_str()
            for name,h in self.data.get("habits",{}).items():
                remind=h.get("remind","")
                if (remind and remind==now and name not in self._reminded_today
                        and today not in h.get("completions",[])):
                    self._reminded_today.add(name)
                    self.after(0,lambda n=name:self._show_reminder(n))

    def _show_reminder(self,name):
        emoji=self.data["habits"].get(name,{}).get("emoji","")
        messagebox.showinfo("Habit Reminder",
                            f"Time to do:\n\n{'  '.join([emoji,name]) if emoji else name}",parent=self)

    def export_csv(self):
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],
                                          title="Export to CSV",parent=self)
        if not path: return
        with open(path,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            w.writerow(["Habit","Category","Type","Frequency","Streak","7d%","30d%","Total","Goal"])
            for name,h in sorted(self.data.get("habits",{}).items()):
                comps=h.get("completions",[])
                w.writerow([name,h.get("category",""),h.get("type",""),h.get("freq",""),
                             streak(comps,self.grace_on()),
                             f"{completion_rate(comps,7)*100:.0f}%",
                             f"{completion_rate(comps,30)*100:.0f}%",
                             len(comps),h.get("goal","")])
        messagebox.showinfo("Exported",f"Saved:\n{path}",parent=self)

    def export_json(self):
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")],
                                          title="Backup Data",parent=self)
        if not path: return
        with open(path,"w",encoding="utf-8") as f: json.dump(self.data,f,indent=2,ensure_ascii=False)
        messagebox.showinfo("Backup Saved",f"Saved:\n{path}",parent=self)

    def import_json(self):
        path=filedialog.askopenfilename(filetypes=[("JSON","*.json")],title="Restore Backup",parent=self)
        if not path: return
        if not messagebox.askyesno("Restore","Replace ALL current data?",parent=self): return
        with open(path,encoding="utf-8") as f: self.data=json.load(f)
        save(self.data); self.show(self.active_tab)
        messagebox.showinfo("Restored","Data restored.",parent=self)


# ─── DASHBOARD ────────────────────────────────────────────────────────────────
class DashboardPage(tk.Frame):
    def __init__(self,parent,app): super().__init__(parent,bg=C['bg']); self.app=app

    def refresh(self):
        for w in self.winfo_children(): w.destroy()
        data=self.app.data; habits=data.get("habits",{})
        settings=data.get("settings",{}); today=today_str(); grace=self.app.grace_on()
        username=settings.get("username","Friend")

        hdr=tk.Frame(self,bg=C['bg']); hdr.pack(fill="x",padx=36,pady=(24,0))
        tk.Label(hdr,text=date.today().strftime("%A, %B %d"),font=F['small'],bg=C['bg'],fg=C['dim']).pack(anchor="w")
        tk.Label(hdr,text=f"{time_greeting()}, {username}.",font=F['title'],bg=C['bg'],fg=C['text']).pack(anchor="w")

        active={n:h for n,h in habits.items() if not h.get("archived")}
        done=sum(1 for h in active.values() if today in h.get("completions",[])); total=len(active)
        best=max((streak(h.get("completions",[]),grace) for h in active.values()),default=0)
        rate7=int(sum(completion_rate(h.get("completions",[]),7) for h in active.values())/total*100) if total else 0

        sf_s=tk.Frame(self,bg=C['bg']); sf_s.pack(fill="x",padx=36,pady=12)
        for lbl,val,color,sub in [("Completed Today",f"{done}/{total}",C['mint'],"habits done"),
                                   ("Best Streak",f"{best}",C['amber'],"days running"),
                                   ("7-day Average",f"{rate7}%",C['violet2'],"completion rate")]:
            card=tk.Frame(sf_s,bg=C['card'],padx=20,pady=14,
                          highlightbackground=C['border'],highlightthickness=1)
            card.pack(side="left",expand=True,fill="both",padx=(0,12))
            tk.Label(card,text=val,font=F['big'],bg=C['card'],fg=color).pack(anchor="w")
            tk.Label(card,text=lbl,font=F['h3'],bg=C['card'],fg=C['text']).pack(anchor="w")
            tk.Label(card,text=sub,font=F['small'],bg=C['card'],fg=C['sub']).pack(anchor="w")

        pf=tk.Frame(self,bg=C['bg'],padx=36); pf.pack(fill="x",pady=(0,4))
        tk.Label(pf,text=f"TODAY'S PROGRESS — {done}/{total} completed",
                 font=F['small'],bg=C['bg'],fg=C['sub']).pack(anchor="w",pady=(0,5))
        bar_bg=tk.Frame(pf,bg=C['card'],height=10,highlightbackground=C['border'],highlightthickness=1)
        bar_bg.pack(fill="x"); bar_bg.pack_propagate(False)
        if total: tk.Frame(bar_bg,bg=C['violet'],height=10).place(relx=0,rely=0,relwidth=done/total,relheight=1)

        # Daily challenge
        incomplete=[n for n,h in active.items() if today not in h.get("completions",[])]
        if incomplete:
            pick=random.choice(incomplete); h_pick=active[pick]
            ch=tk.Frame(self,bg=C['card2'],padx=20,pady=10,
                        highlightbackground=C['violet'],highlightthickness=1)
            ch.pack(fill="x",padx=36,pady=(6,0))
            tk.Label(ch,text="DAILY CHALLENGE",font=F['small'],bg=C['card2'],fg=C['amber']).pack(anchor="w")
            emoji=h_pick.get("emoji","")
            tk.Label(ch,text=f"{emoji}  {pick}" if emoji else pick,
                     font=F['h2'],bg=C['card2'],fg=C['text']).pack(anchor="w")
            btn(ch,"Do It Now",lambda n=pick:self._toggle(n),
                bg=C['amber'],fg=C['bg'],pad=(12,5)).pack(anchor="w",pady=(6,0))

        divider(self,C['border'])

        tb=tk.Frame(self,bg=C['bg'],padx=36); tb.pack(fill="x",pady=(0,6))
        tk.Label(tb,text="TODAY'S HABITS",font=F['small'],bg=C['bg'],fg=C['sub']).pack(side="left")
        btn(tb,"+ New Habit",self._new_habit,bg=C['violet'],pad=(12,4)).pack(side="right")
        self.search_var=tk.StringVar()
        se=tk.Entry(tb,textvariable=self.search_var,font=F['label'],bg=C['card'],fg=C['text'],
                    insertbackground=C['text'],relief="flat",
                    highlightbackground=C['border'],highlightthickness=1,width=18)
        se.pack(side="right",padx=10,ipady=4)
        tk.Label(tb,text="🔍",font=F['body'],bg=C['bg'],fg=C['sub']).pack(side="right")
        self.search_var.trace_add("write",lambda *_:self._filter())

        cat_f=tk.Frame(self,bg=C['bg'],padx=36); cat_f.pack(fill="x",pady=(0,4))
        self.cat_filter=tk.StringVar(value="All")
        cats=["All"]+sorted({h.get("category","Other") for h in active.values()})
        for cat in cats:
            tk.Radiobutton(cat_f,text=cat,variable=self.cat_filter,value=cat,
                           font=F['small'],bg=C['bg'],fg=C['sub'],selectcolor=C['bg'],
                           activebackground=C['bg'],command=self._filter
                           ).pack(side="left",padx=(0,8))

        self.list_sf=ScrollFrame(self,bg=C['bg'])
        self.list_sf.pack(fill="both",expand=True,padx=36,pady=(0,16))
        self.list_p=self.list_sf.inner
        if not active:
            tk.Label(self.list_p,text="No habits yet.\nClick '+ New Habit' to begin.",
                     font=F['body'],bg=C['bg'],fg=C['dim'],justify="center",pady=60).pack()
        else:
            self._render(active)

    def _filter(self):
        for w in self.list_p.winfo_children(): w.destroy()
        active={n:h for n,h in self.app.data.get("habits",{}).items() if not h.get("archived")}
        q=self.search_var.get().lower(); cat=self.cat_filter.get()
        filtered={n:h for n,h in active.items()
                  if q in n.lower() and (cat=="All" or h.get("category","Other")==cat)}
        if filtered: self._render(filtered)
        else: tk.Label(self.list_p,text="No habits match.",font=F['body'],bg=C['bg'],fg=C['dim'],pady=30).pack()

    def _render(self, habits):
        today=today_str(); now_t=datetime.now().strftime("%H:%M")
        for name,h in sorted(habits.items(),key=lambda x:(today not in x[1].get("completions",[]),x[0])):
            self._row(self.list_p,name,h,today,now_t)

    def _row(self,parent,name,h,today,now_t):
        color=h.get("color",C['violet']); emoji=h.get("emoji","")
        comps=h.get("completions",[]); done=today in comps
        s=streak(comps,self.app.grace_on()); remind=h.get("remind","")
        urgent=remind and not done and now_t>=remind

        row=tk.Frame(parent,bg=C['card'],
                     highlightbackground=color if done else (C['coral'] if urgent else C['border']),
                     highlightthickness=1)
        row.pack(fill="x",pady=4)
        tk.Frame(row,bg=color,width=4).pack(side="left",fill="y")
        inner=tk.Frame(row,bg=C['card'],padx=14,pady=10); inner.pack(side="left",fill="both",expand=True)

        top=tk.Frame(inner,bg=C['card']); top.pack(fill="x")
        tk.Label(top,text=f"{emoji}  {name}" if emoji else name,
                 font=F['h2'],bg=C['card'],fg=C['text']).pack(side="left")
        tag(top,h.get('type','build'),C['mint'] if h.get('type')=='build' else C['coral']).pack(side="left",padx=5)
        tag(top,h.get('freq','daily'),C['dim']).pack(side="left",padx=2)
        if h.get('category'): tag(top,h['category'],C['sky']).pack(side="left",padx=2)
        if urgent: tk.Label(top,text=f"  ⏰ {remind}",font=F['small'],bg=C['card'],fg=C['coral']).pack(side="left")

        info=tk.Frame(inner,bg=C['card']); info.pack(fill="x",pady=(4,0))
        sc=C['amber'] if s>=7 else (C['mint'] if s>=3 else C['sub'])
        tk.Label(info,text=f"🔥 {s} day streak",font=F['label'],bg=C['card'],fg=sc).pack(side="left")
        if h.get('goal'): tk.Label(info,text=f"  ·  {h['goal']}",font=F['label'],bg=C['card'],fg=C['sub']).pack(side="left")

        dots=tk.Frame(inner,bg=C['card']); dots.pack(anchor="w",pady=(6,0))
        for d in last_n_days(7):
            f=tk.Frame(dots,bg=color if d in comps else C['border'],width=12,height=12)
            f.pack(side="left",padx=2); Tooltip(f,d)

        bf=tk.Frame(row,bg=C['card'],padx=8); bf.pack(side="right",fill="y")
        cb_bg=color if done else C['card2']; cb_fg=C['bg'] if done else C['sub']
        btn(bf,"✓ Done" if done else "Mark Done",lambda n=name:self._toggle(n),
            bg=cb_bg,fg=cb_fg,pad=(12,7)).pack(pady=(10,3))
        btn(bf,"⏱",lambda n=name:FocusTimer(self.app,n),bg=C['card'],fg=C['sub'],pad=(8,4)).pack(pady=2)
        btn(bf,"…",lambda n=name,h2=h:self._backfill(n,h2),bg=C['card'],fg=C['dim'],pad=(8,4)).pack(pady=(2,10))

    def _toggle(self,name):
        today=today_str(); comps=self.app.data["habits"][name].setdefault("completions",[])
        added=today not in comps
        if added: comps.append(today);(self.bell() if self.app.sound_on() else None)
        else: comps.remove(today)
        self.app.push_undo(name,today,added); save(self.app.data); self.refresh()

    def _backfill(self,name,h):
        dlg=BackfillDialog(self.app,name,h.get("completions",[]))
        self.wait_window(dlg)
        if dlg.result:
            comps=self.app.data["habits"][name].setdefault("completions",[])
            comp_set=set(comps)
            for d,checked in dlg.result.items():
                if checked and d not in comp_set: comps.append(d)
                elif not checked and d in comp_set: comps.remove(d)
            save(self.app.data); self.refresh()

    def _new_habit(self):
        dlg=HabitDialog(self.app)
        self.wait_window(dlg)
        if dlg.result:
            r=dlg.result; n=r.pop("name"); r["completions"]=[]
            self.app.data["habits"][n]=r; save(self.app.data); self.refresh()


# ─── HABITS PAGE ──────────────────────────────────────────────────────────────
class HabitsPage(tk.Frame):
    def __init__(self,parent,app): super().__init__(parent,bg=C['bg']); self.app=app

    def refresh(self):
        for w in self.winfo_children(): w.destroy()
        habits=self.app.data.get("habits",{}); show_arch=self.app.data["settings"].get("show_archived",False)
        hdr=tk.Frame(self,bg=C['bg']); hdr.pack(fill="x",padx=36,pady=(28,8))
        tk.Label(hdr,text="My Habits",font=F['title'],bg=C['bg'],fg=C['text']).pack(side="left")
        btn(hdr,"+ Add Habit",self._new,bg=C['violet']).pack(side="right")
        btn(hdr,"Show Archived" if not show_arch else "Hide Archived",
            self._toggle_arch,bg=C['card'],fg=C['sub'],pad=(10,6)).pack(side="right",padx=8)

        sf=ScrollFrame(self,bg=C['bg']); sf.pack(fill="both",expand=True,padx=36,pady=(0,24))
        active={n:h for n,h in habits.items() if not h.get("archived")}
        archived={n:h for n,h in habits.items() if h.get("archived")}

        if active: section_header(sf.inner,f"ACTIVE  ({len(active)})"); [self._card(sf.inner,n,h,False) for n,h in sorted(active.items())]
        if show_arch and archived: section_header(sf.inner,f"ARCHIVED  ({len(archived)})"); [self._card(sf.inner,n,h,True) for n,h in sorted(archived.items())]
        if not active and not (show_arch and archived):
            tk.Label(sf.inner,text="No habits yet.",font=F['body'],bg=C['bg'],fg=C['dim'],pady=60).pack()

    def _card(self,parent,name,h,archived):
        color=h.get("color",C['violet']); comps=h.get("completions",[])
        s=streak(comps,self.app.grace_on()); r7=int(completion_rate(comps,7)*100); r30=int(completion_rate(comps,30)*100)
        bg=C['surface'] if archived else C['card']
        card=tk.Frame(parent,bg=bg,highlightbackground=C['border'],highlightthickness=1); card.pack(fill="x",pady=5)
        tk.Frame(card,bg=color if not archived else C['dim'],width=4).pack(side="left",fill="y")
        body=tk.Frame(card,bg=bg,padx=18,pady=14); body.pack(side="left",fill="both",expand=True)
        row1=tk.Frame(body,bg=bg); row1.pack(fill="x")
        emoji=h.get("emoji","")
        tk.Label(row1,text=f"{emoji}  {name}" if emoji else name,font=F['h2'],bg=bg,
                 fg=C['sub'] if archived else C['text']).pack(side="left")
        tag(row1,h.get('type','build'),C['mint'] if h.get('type')=='build' else C['coral']).pack(side="left",padx=6)
        tag(row1,h.get('freq','daily'),C['dim']).pack(side="left",padx=2)
        if h.get('category'): tag(row1,h['category'],C['sky']).pack(side="left",padx=2)
        if h.get('remind'): tk.Label(row1,text=f"⏰{h['remind']}",font=F['small'],bg=bg,fg=C['sub']).pack(side="left",padx=6)
        row2=tk.Frame(body,bg=bg); row2.pack(fill="x",pady=(6,0))
        for t in [f"🔥 {s}d",f"7d:{r7}%",f"30d:{r30}%",f"Total:{len(comps)}"]:
            tk.Label(row2,text=t+"  ",font=F['label'],bg=bg,fg=C['sub']).pack(side="left")
        if h.get('goal'): tk.Label(body,text=f"Goal: {h['goal']}",font=F['label'],bg=bg,fg=C['violet3']).pack(anchor="w",pady=(4,0))
        dots=tk.Frame(body,bg=bg); dots.pack(anchor="w",pady=(8,0))
        tk.Label(dots,text="30d: ",font=F['small'],bg=bg,fg=C['dim']).pack(side="left")
        for d in last_n_days(30):
            f=tk.Frame(dots,bg=color if d in set(comps) else C['border'],width=10,height=10)
            f.pack(side="left",padx=1); Tooltip(f,d)
        bf=tk.Frame(card,bg=bg,padx=10); bf.pack(side="right",fill="y",pady=8)
        if not archived:
            btn(bf,"Edit",lambda n=name,h2=h:self._edit(n,h2),bg=C['card2'],fg=C['sub'],pad=(10,5)).pack(pady=2)
            btn(bf,"Archive",lambda n=name:self._archive(n,True),bg=C['card2'],fg=C['amber'],pad=(10,5)).pack(pady=2)
            btn(bf,"Timer",lambda n=name:FocusTimer(self.app,n),bg=C['card2'],fg=C['sky'],pad=(10,5)).pack(pady=2)
        else:
            btn(bf,"Restore",lambda n=name:self._archive(n,False),bg=C['card2'],fg=C['mint'],pad=(10,5)).pack(pady=2)
        btn(bf,"Delete",lambda n=name:self._delete(n),bg="#2a1520",fg=C['coral'],pad=(10,5)).pack(pady=2)

    def _toggle_arch(self):
        s=self.app.data["settings"]; s["show_archived"]=not s.get("show_archived",False)
        save(self.app.data); self.refresh()

    def _archive(self,name,state):
        self.app.data["habits"][name]["archived"]=state; save(self.app.data); self.refresh()

    def _new(self):
        dlg=HabitDialog(self.app); self.wait_window(dlg)
        if dlg.result:
            r=dlg.result; n=r.pop("name"); r["completions"]=[]
            self.app.data["habits"][n]=r; save(self.app.data); self.refresh()

    def _edit(self,name,h):
        dlg=HabitDialog(self.app,"Edit Habit",
                        {"name":name,**{k:h.get(k,'') for k in ['type','freq','goal','emoji','color','category','remind','target']}})
        self.wait_window(dlg)
        if dlg.result:
            r=dlg.result; new_name=r.pop("name")
            old=self.app.data["habits"].pop(name); old.update(r)
            self.app.data["habits"][new_name]=old; save(self.app.data); self.refresh()

    def _delete(self,name):
        if messagebox.askyesno("Delete",f'Delete "{name}" and all data?',parent=self):
            del self.app.data["habits"][name]; save(self.app.data); self.refresh()


# ─── ANALYTICS ────────────────────────────────────────────────────────────────
class AnalyticsPage(tk.Frame):
    def __init__(self,parent,app): super().__init__(parent,bg=C['bg']); self.app=app

    def refresh(self):
        for w in self.winfo_children(): w.destroy()
        habits={n:h for n,h in self.app.data.get("habits",{}).items() if not h.get("archived")}
        hdr=tk.Frame(self,bg=C['bg']); hdr.pack(fill="x",padx=36,pady=(28,8))
        tk.Label(hdr,text="Analytics",font=F['title'],bg=C['bg'],fg=C['text']).pack(side="left")
        btn(hdr,"Export CSV",self.app.export_csv,bg=C['card'],fg=C['sub'],pad=(10,6)).pack(side="right")
        if not habits:
            tk.Label(self,text="No habits to analyse yet.",font=F['body'],bg=C['bg'],fg=C['dim'],pady=60).pack(); return

        self.period=tk.StringVar(value="week")
        tf=tk.Frame(self,bg=C['bg'],padx=36); tf.pack(fill="x",pady=(0,4))
        for val,lbl in [("week","Last 7 Days"),("month","Last 30 Days"),("all","All Time")]:
            tk.Radiobutton(tf,text=lbl,variable=self.period,value=val,font=F['small'],
                           bg=C['bg'],fg=C['text'],selectcolor=C['card'],
                           activebackground=C['bg'],command=self.refresh).pack(side="left",padx=(0,12))

        sf=ScrollFrame(self,bg=C['bg']); sf.pack(fill="both",expand=True,padx=36,pady=(0,24))
        p=sf.inner
        days=(last_n_days(7) if self.period.get()=="week"
              else last_n_days(30) if self.period.get()=="month" else None)
        date_set=set(days) if days else None; n=len(days) if days else None

        section_header(p,"SUMMARY"); self._summary(p,habits,date_set,n)
        section_header(p,"30-DAY HEATMAP"); self._heatmap(p,habits)
        section_header(p,"PER-HABIT HISTORY")
        for name,h in sorted(habits.items()): self._habit_bar(p,name,h)
        section_header(p,"STREAK LEADERBOARD"); self._leaderboard(p,habits)
        section_header(p,"BEST DAY OF WEEK"); self._best_day(p,habits)
        section_header(p,"WEEKLY CHART"); self._weekly(p,habits)

    def _summary(self,parent,habits,date_set,n):
        grace=self.app.grace_on(); total_habits=len(habits)
        if date_set and n:
            tp=total_habits*n; td=sum(len(set(h.get("completions",[])) & date_set) for h in habits.values())
            overall=int(td/tp*100) if tp else 0
        else:
            td=sum(len(h.get("completions",[])) for h in habits.values()); overall=100
        best_s=max((streak(h.get("completions",[]),grace) for h in habits.values()),default=0)
        perfect=sum(1 for h in habits.values() if completion_rate(h.get("completions",[]),7)==1.0)
        row=tk.Frame(parent,bg=C['bg']); row.pack(fill="x",pady=4)
        for lbl,val,color in [("Overall Rate",f"{overall}%",C['violet2']),
                               ("Total Completions",str(td),C['mint']),
                               ("Best Streak",f"{best_s}d",C['amber']),
                               ("Perfect 7-day",str(perfect),C['sky'])]:
            box=tk.Frame(row,bg=C['card'],padx=14,pady=12,highlightbackground=C['border'],highlightthickness=1)
            box.pack(side="left",expand=True,fill="both",padx=(0,8))
            tk.Label(box,text=val,font=("Georgia",20,"bold"),bg=C['card'],fg=color).pack(anchor="w")
            tk.Label(box,text=lbl,font=F['small'],bg=C['card'],fg=C['sub']).pack(anchor="w")

    def _heatmap(self,parent,habits):
        card=tk.Frame(parent,bg=C['card'],padx=16,pady=14,highlightbackground=C['border'],highlightthickness=1)
        card.pack(fill="x",pady=4)
        days=last_n_days(30); n_h=len(habits); all_c={}
        for h in habits.values():
            for d in h.get("completions",[]): all_c[d]=all_c.get(d,0)+1
        row=tk.Frame(card,bg=C['card']); row.pack(anchor="w")
        for d in days:
            frac=all_c.get(d,0)/n_h if n_h else 0
            color=("#1e1a3a" if frac==0 else "#3d2d8a" if frac<0.33 else "#5b44c4" if frac<0.66 else C['violet'])
            cell=tk.Frame(row,bg=color,width=20,height=20); cell.pack(side="left",padx=1)
            Tooltip(cell,f"{d}: {all_c.get(d,0)}/{n_h}")
        lbl_row=tk.Frame(card,bg=C['card']); lbl_row.pack(anchor="w",pady=(4,0))
        for i,d in enumerate(days):
            txt=date.fromisoformat(d).strftime("%d") if i%5==0 else "  "
            tk.Label(lbl_row,text=txt,font=F['small'],bg=C['card'],fg=C['dim'],width=2).pack(side="left",padx=1)

    def _habit_bar(self,parent,name,h):
        comps=set(h.get("completions",[])); color=h.get("color",C['violet'])
        emoji=h.get("emoji",""); days=last_n_days(30)
        pct=int(completion_rate(list(comps),30)*100); s=streak(list(comps),self.app.grace_on())
        row=tk.Frame(parent,bg=C['card'],padx=14,pady=8,highlightbackground=C['border'],highlightthickness=1)
        row.pack(fill="x",pady=2)
        lf=tk.Frame(row,bg=C['card'],width=160); lf.pack(side="left"); lf.pack_propagate(False)
        tk.Label(lf,text=f"{emoji} {name}" if emoji else name,font=F['body'],bg=C['card'],fg=C['text'],anchor="w").pack(fill="x")
        bars=tk.Frame(row,bg=C['card']); bars.pack(side="left",fill="x",expand=True,padx=6)
        for d in days: tk.Frame(bars,bg=color if d in comps else C['border'],width=10,height=22).pack(side="left",padx=1)
        tk.Label(row,text=f" {pct}%  🔥{s}",font=F['label'],bg=C['card'],fg=C['sub'],width=10,anchor="e").pack(side="right")

    def _leaderboard(self,parent,habits):
        grace=self.app.grace_on()
        rows=sorted([(n,streak(h.get("completions",[]),grace),h.get("color",C['violet']),h.get("emoji",""))
                     for n,h in habits.items()],key=lambda x:x[1],reverse=True)
        card=tk.Frame(parent,bg=C['card'],padx=18,pady=12,highlightbackground=C['border'],highlightthickness=1)
        card.pack(fill="x",pady=4)
        medals=["🥇","🥈","🥉"]; max_s=rows[0][1] if rows and rows[0][1] else 1
        for i,(name,s,color,emoji) in enumerate(rows[:8]):
            row=tk.Frame(card,bg=C['card']); row.pack(fill="x",pady=2)
            tk.Label(row,text=medals[i] if i<3 else f" {i+1}.",font=F['body'],bg=C['card'],fg=C['text'],width=3).pack(side="left")
            tk.Frame(row,bg=color,width=4,height=18).pack(side="left",padx=6)
            tk.Label(row,text=f"{emoji} {name}" if emoji else name,font=F['body'],bg=C['card'],fg=C['text']).pack(side="left")
            bar_bg=tk.Frame(row,bg=C['border'],height=8); bar_bg.pack(side="left",fill="x",expand=True,padx=10)
            bar_bg.pack_propagate(False)
            if s: tk.Frame(bar_bg,bg=color,height=8).place(relx=0,rely=0,relwidth=s/max_s,relheight=1)
            tk.Label(row,text=f"🔥{s}d",font=F['label'],bg=C['card'],fg=C['amber'],width=6,anchor="e").pack(side="right")

    def _best_day(self,parent,habits):
        card=tk.Frame(parent,bg=C['card'],padx=18,pady=14,highlightbackground=C['border'],highlightthickness=1)
        card.pack(fill="x",pady=4)
        dow=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        counts={d:0 for d in dow}; totals={d:0 for d in dow}
        for h in habits.values():
            for ds in h.get("completions",[]):
                counts[dow[date.fromisoformat(ds).weekday()]]+=1
        for i in range(90): totals[dow[(date.today()-timedelta(i)).weekday()]]+=1
        max_r=max((counts[d]/totals[d] if totals[d] else 0 for d in dow),default=1) or 1
        row=tk.Frame(card,bg=C['card']); row.pack(anchor="w")
        for d in dow:
            r=counts[d]/totals[d] if totals[d] else 0
            cf=tk.Frame(row,bg=C['card']); cf.pack(side="left",padx=5)
            bh=int((r/max_r)*60) if max_r else 0
            tk.Frame(cf,bg=C['card'],height=60-bh).pack()
            tk.Frame(cf,bg=C['violet'] if r==max_r else C['border2'],width=30,height=max(bh,3)).pack()
            tk.Label(cf,text=f"{int(r*100)}%",font=F['small'],bg=C['card'],fg=C['sub']).pack()
            tk.Label(cf,text=d,font=F['small'],bg=C['card'],fg=C['text']).pack()

    def _weekly(self,parent,habits):
        card=tk.Frame(parent,bg=C['card'],padx=18,pady=14,highlightbackground=C['border'],highlightthickness=1)
        card.pack(fill="x",pady=4)
        today_d=date.today(); weeks=[]
        for w in range(7,-1,-1):
            ws=today_d-timedelta(days=today_d.weekday()+7*w)
            days=[(ws+timedelta(d)).isoformat() for d in range(7)]
            tp=len(habits)*7
            done=sum(1 for h in habits.values() for d in days if d in set(h.get("completions",[])))
            weeks.append((ws.strftime("%b %d"),done/tp if tp else 0))
        max_h=80; cf=tk.Frame(card,bg=C['card']); cf.pack(anchor="w")
        for label,pct in weeks:
            col=tk.Frame(cf,bg=C['card']); col.pack(side="left",padx=4)
            h=int(pct*max_h)
            tk.Frame(col,bg=C['card'],height=max_h-h).pack()
            tk.Frame(col,bg=C['violet'] if pct>0 else C['border'],width=36,height=max(h,4)).pack()
            tk.Label(col,text=f"{int(pct*100)}%",font=F['small'],bg=C['card'],fg=C['sub']).pack()
            tk.Label(col,text=label,font=("Courier New",7),bg=C['card'],fg=C['dim']).pack()


# ─── JOURNAL ──────────────────────────────────────────────────────────────────
class JournalPage(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=C['bg']); self.app=app; self.selected_date=today_str()

    def refresh(self):
        for w in self.winfo_children(): w.destroy()
        journal=self.app.data.setdefault("journal",{})
        hdr=tk.Frame(self,bg=C['bg']); hdr.pack(fill="x",padx=36,pady=(28,12))
        tk.Label(hdr,text="Journal",font=F['title'],bg=C['bg'],fg=C['text']).pack(anchor="w")

        main=tk.Frame(self,bg=C['bg']); main.pack(fill="both",expand=True,padx=36,pady=(0,24))
        left=tk.Frame(main,bg=C['surface'],width=230,highlightbackground=C['border'],highlightthickness=1)
        left.pack(side="left",fill="y"); left.pack_propagate(False)
        tk.Label(left,text="ENTRIES",font=F['small'],bg=C['surface'],fg=C['sub'],pady=10).pack()
        tk.Frame(left,bg=C['border'],height=1).pack(fill="x")
        btn(left,"+ New Entry",self._new,bg=C['violet'],pad=(12,7)).pack(fill="x",padx=12,pady=8)
        sf=ScrollFrame(left,bg=C['surface']); sf.pack(fill="both",expand=True)
        entries=sorted(journal.keys(),reverse=True)
        if not entries: tk.Label(sf.inner,text="No entries yet.",font=F['small'],bg=C['surface'],fg=C['dim'],pady=20).pack()
        for d in entries: self._entry_btn(sf.inner,d,journal[d])

        right=tk.Frame(main,bg=C['bg']); right.pack(side="left",fill="both",expand=True,padx=(14,0))
        if self.selected_date in journal: self._show_entry(right,self.selected_date,journal[self.selected_date])
        else: tk.Label(right,text="Select or create an entry.",font=F['body'],bg=C['bg'],fg=C['dim'],pady=60).pack()

    def _entry_btn(self,parent,d,entry):
        sel=d==self.selected_date
        mood_icon={"great":"😊","good":"🙂","okay":"😐","bad":"😔"}.get(entry.get("mood","good"),"")
        card=tk.Frame(parent,bg=C['card'] if sel else C['surface'],padx=10,pady=7,cursor="hand2",
                      highlightbackground=C['violet'] if sel else C['surface'],highlightthickness=1 if sel else 0)
        card.pack(fill="x",pady=2)
        card.bind("<Button-1>",lambda e,dt=d:self._select(dt))
        dt=date.fromisoformat(d)
        row=tk.Frame(card,bg=card['bg']); row.pack(fill="x")
        row.bind("<Button-1>",lambda e,dt=d:self._select(dt))
        tk.Label(row,text=dt.strftime("%b %d, %Y"),cursor="hand2",
                 font=("Courier New",9,"bold") if sel else F['label'],
                 bg=card['bg'],fg=C['violet2'] if sel else C['text']).pack(side="left")
        tk.Label(row,text=mood_icon,font=F['body'],bg=card['bg']).pack(side="right")
        preview=entry.get("text","")[:38]+("…" if len(entry.get("text",""))>38 else "")
        tk.Label(card,text=preview,font=F['small'],cursor="hand2",bg=card['bg'],fg=C['sub']).pack(anchor="w")
        for w in card.winfo_children(): w.bind("<Button-1>",lambda e,dt=d:self._select(dt))

    def _select(self,d): self.selected_date=d; self.refresh()

    def _show_entry(self,parent,d,entry):
        dt=date.fromisoformat(d)
        tk.Label(parent,text=dt.strftime("%A, %B %d %Y"),font=F['h1'],bg=C['bg'],fg=C['text']
                 ).pack(anchor="w",pady=(4,12))
        mf=tk.Frame(parent,bg=C['bg']); mf.pack(anchor="w",pady=(0,8))
        tk.Label(mf,text="MOOD  ",font=F['small'],bg=C['bg'],fg=C['sub']).pack(side="left")
        self.mood_var=tk.StringVar(value=entry.get("mood","good"))
        for emoji,val in [("😊","great"),("🙂","good"),("😐","okay"),("😔","bad")]:
            tk.Radiobutton(mf,text=emoji,variable=self.mood_var,value=val,
                           font=("Courier New",14),bg=C['bg'],selectcolor=C['bg'],
                           activebackground=C['bg'],relief="flat",cursor="hand2").pack(side="left",padx=2)

        tf2=tk.Frame(parent,bg=C['bg']); tf2.pack(anchor="w",pady=(0,8))
        tk.Label(tf2,text="TAGS  ",font=F['small'],bg=C['bg'],fg=C['sub']).pack(side="left")
        self.tags_var=tk.StringVar(value=entry.get("tags",""))
        tk.Entry(tf2,textvariable=self.tags_var,font=F['label'],width=28,bg=C['card'],fg=C['text'],
                 insertbackground=C['text'],relief="flat",highlightbackground=C['border'],
                 highlightthickness=1).pack(side="left",ipady=4)
        tk.Label(tf2,text=" (comma-separated)",font=F['small'],bg=C['bg'],fg=C['dim']).pack(side="left")

        tk.Label(parent,text="REFLECTION",font=F['small'],bg=C['bg'],fg=C['sub']).pack(anchor="w",pady=(4,4))
        self.text_widget=tk.Text(parent,font=F['body'],bg=C['card'],fg=C['text'],
                                  insertbackground=C['text'],relief="flat",
                                  highlightbackground=C['border'],highlightthickness=1,
                                  padx=14,pady=12,wrap="word",height=10)
        self.text_widget.pack(fill="both",expand=True)
        self.text_widget.insert("1.0",entry.get("text",""))

        habits=self.app.data.get("habits",{})
        active_h={n:h for n,h in habits.items() if not h.get("archived")}
        if active_h:
            tk.Label(parent,text="HABIT NOTES",font=F['small'],bg=C['bg'],fg=C['sub']).pack(anchor="w",pady=(10,4))
            hnotes=entry.get("habit_notes",{}); self.hnote_widgets={}
            for name in sorted(active_h.keys()):
                hrow=tk.Frame(parent,bg=C['bg']); hrow.pack(fill="x",pady=2)
                color=active_h[name].get("color",C['violet'])
                tk.Frame(hrow,bg=color,width=3).pack(side="left",fill="y",padx=(0,8))
                tk.Label(hrow,text=name,font=F['label'],bg=C['bg'],fg=C['text'],width=16,anchor="w").pack(side="left")
                var=tk.StringVar(value=hnotes.get(name,""))
                tk.Entry(hrow,textvariable=var,font=F['label'],bg=C['card'],fg=C['text'],
                         relief="flat",insertbackground=C['text'],
                         highlightbackground=C['border'],highlightthickness=1
                         ).pack(side="left",fill="x",expand=True,ipady=4)
                self.hnote_widgets[name]=var

        bf=tk.Frame(parent,bg=C['bg']); bf.pack(fill="x",pady=10)
        btn(bf,"Save Entry",lambda:self._save(d),bg=C['violet']).pack(side="left")
        btn(bf,"Delete",lambda:self._delete(d),bg="#2a1520",fg=C['coral']).pack(side="left",padx=8)

    def _new(self):
        d=today_str()
        self.app.data["journal"].setdefault(d,{"text":"","mood":"good","tags":"","habit_notes":{}})
        save(self.app.data); self.selected_date=d; self.refresh()

    def _save(self,d):
        hnotes={k:v.get() for k,v in self.hnote_widgets.items()} if hasattr(self,"hnote_widgets") else {}
        self.app.data["journal"][d]={"text":self.text_widget.get("1.0","end-1c"),
                                      "mood":self.mood_var.get(),"tags":self.tags_var.get().strip(),
                                      "habit_notes":hnotes}
        save(self.app.data); messagebox.showinfo("Saved","Entry saved.",parent=self); self.refresh()

    def _delete(self,d):
        if messagebox.askyesno("Delete","Delete this entry?",parent=self):
            del self.app.data["journal"][d]; save(self.app.data)
            self.selected_date=today_str(); self.refresh()


# ─── SETTINGS ─────────────────────────────────────────────────────────────────
class SettingsPage(tk.Frame):
    def __init__(self,parent,app): super().__init__(parent,bg=C['bg']); self.app=app

    def refresh(self):
        for w in self.winfo_children(): w.destroy()
        s=self.app.data.get("settings",DEFAULT_SETTINGS.copy())
        hdr=tk.Frame(self,bg=C['bg']); hdr.pack(fill="x",padx=36,pady=(28,16))
        tk.Label(hdr,text="Settings",font=F['title'],bg=C['bg'],fg=C['text']).pack(anchor="w")

        sf=ScrollFrame(self,bg=C['bg']); sf.pack(fill="both",expand=True,padx=36,pady=(0,24))
        p=sf.inner

        section_header(p,"PROFILE")
        card=tk.Frame(p,bg=C['card'],padx=20,pady=16,highlightbackground=C['border'],highlightthickness=1)
        card.pack(fill="x",pady=4)
        tk.Label(card,text="Your Name",font=F['body'],bg=C['card'],fg=C['text']).pack(anchor="w")
        self.name_var=tk.StringVar(value=s.get("username","Friend"))
        tk.Entry(card,textvariable=self.name_var,font=F['body'],bg=C['bg'],fg=C['text'],
                 insertbackground=C['text'],relief="flat",
                 highlightbackground=C['border'],highlightthickness=1).pack(fill="x",pady=(6,0),ipady=7)

        section_header(p,"BEHAVIOUR")
        bcard=tk.Frame(p,bg=C['card'],padx=20,pady=16,highlightbackground=C['border'],highlightthickness=1)
        bcard.pack(fill="x",pady=4)
        self.grace_var=tk.BooleanVar(value=s.get("streak_grace",False))
        self.sound_var=tk.BooleanVar(value=s.get("sound",True))
        self.arch_var=tk.BooleanVar(value=s.get("show_archived",False))
        for var,lbl,sub in [
            (self.grace_var,"Streak Grace Day","One missed day per week won't break your streak"),
            (self.sound_var,"Completion Sound","Play a bell when a habit is marked done"),
            (self.arch_var,"Show Archived Habits","Display archived habits in My Habits"),
        ]:
            row=tk.Frame(bcard,bg=C['card']); row.pack(fill="x",pady=5)
            tk.Checkbutton(row,variable=var,font=F['body'],bg=C['card'],fg=C['text'],
                           selectcolor=C['border'],activebackground=C['card'],text=lbl).pack(side="left")
            tk.Label(row,text=f"  —  {sub}",font=F['small'],bg=C['card'],fg=C['sub']).pack(side="left")

        section_header(p,"DATA MANAGEMENT")
        dcard=tk.Frame(p,bg=C['card'],padx=20,pady=16,highlightbackground=C['border'],highlightthickness=1)
        dcard.pack(fill="x",pady=4)
        row1=tk.Frame(dcard,bg=C['card']); row1.pack(fill="x",pady=4)
        btn(row1,"Export CSV",self.app.export_csv,bg=C['card2'],fg=C['sub'],pad=(12,7)).pack(side="left",padx=(0,8))
        btn(row1,"Backup JSON",self.app.export_json,bg=C['card2'],fg=C['sub'],pad=(12,7)).pack(side="left",padx=(0,8))
        btn(row1,"Restore Backup",self.app.import_json,bg=C['card2'],fg=C['amber'],pad=(12,7)).pack(side="left")
        tk.Label(dcard,text=f"Data file: {DATA_FILE}",font=F['small'],bg=C['card'],fg=C['dim']).pack(anchor="w",pady=(10,0))

        section_header(p,"STATISTICS")
        habits=self.app.data.get("habits",{})
        active=sum(1 for h in habits.values() if not h.get("archived"))
        arch=sum(1 for h in habits.values() if h.get("archived"))
        all_c=sum(len(h.get("completions",[])) for h in habits.values())
        j_count=len(self.app.data.get("journal",{}))
        scard=tk.Frame(p,bg=C['card'],padx=20,pady=14,highlightbackground=C['border'],highlightthickness=1)
        scard.pack(fill="x",pady=4)
        row2=tk.Frame(scard,bg=C['card']); row2.pack(fill="x")
        for lbl,val in [("Active Habits",str(active)),("Archived",str(arch)),
                        ("Total Completions",str(all_c)),("Journal Entries",str(j_count))]:
            box=tk.Frame(row2,bg=C['card2'],padx=14,pady=10,highlightbackground=C['border'],highlightthickness=1)
            box.pack(side="left",expand=True,fill="both",padx=(0,6))
            tk.Label(box,text=val,font=("Georgia",18,"bold"),bg=C['card2'],fg=C['violet2']).pack(anchor="w")
            tk.Label(box,text=lbl,font=F['small'],bg=C['card2'],fg=C['sub']).pack(anchor="w")

        btn(p,"Save Settings",self._save,bg=C['violet'],pad=(20,10)).pack(anchor="w",pady=16)

    def _save(self):
        s=self.app.data.setdefault("settings",DEFAULT_SETTINGS.copy())
        s["username"]=self.name_var.get().strip() or "Friend"
        s["streak_grace"]=self.grace_var.get(); s["sound"]=self.sound_var.get()
        s["show_archived"]=self.arch_var.get()
        save(self.app.data); messagebox.showinfo("Saved","Settings saved.",parent=self); self.refresh()


if __name__ == "__main__":
    app=App(); app.mainloop()