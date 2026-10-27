import sys, os, json, uuid, calendar
from datetime import datetime, date, timedelta
from PySide6.QtCore import Qt, QTimer, QDate, QTime, Signal
from PySide6.QtWidgets import *
from PySide6.QtGui import QColor, QIcon, QAction, QPainter, QFont, QTextCharFormat, QPalette

APP = "BEST CHECKLIST"
DATA_DIR = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "MiniHomeChecklist")
DATA_FILE = os.path.join(DATA_DIR, "tasks.json")
CATS = [{"name":"일상","emoji":"🌿","color":"#78b99a"},{"name":"업무","emoji":"💼","color":"#7c9ee8"},{"name":"공부","emoji":"📚","color":"#b39be8"},{"name":"취미","emoji":"🎨","color":"#f0ad7a"},{"name":"건강","emoji":"💪","color":"#e58e9b"}]
def stamp(): return datetime.now().strftime("%Y-%m-%d %H:%M")
def newtask():
    today=date.today().isoformat()
    return {"id":str(uuid.uuid4()),"title":"","category":"일상","start_date":today,"due":today,"date_enabled":False,"show_in_calendar":False,"priority":"보통","done":False,"created":stamp(),"repeat":{"type":"없음","weekdays":[],"monthday":1,"time":"09:00","time_none":False},"reminder":"","reminder_at":"","reminded":[],"subtasks":[],"history":[],"order":0}

class ClickLabel(QLabel):
    clicked = Signal()
    def mousePressEvent(self,event):
        self.clicked.emit(); super().mousePressEvent(event)

class TaskStrip(QFrame):
    clicked = Signal()
    def __init__(self, text, color, tooltip="", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        c=QColor(color)
        self.setStyleSheet(f"QFrame{{background:rgba({c.red()},{c.green()},{c.blue()},0.88);border:1px solid rgba(60,65,80,0.35);border-radius:6px}} QFrame:hover{{border:2px solid #555d70}} QLabel{{background:transparent;color:#202435;border:0;font-size:10pt;font-weight:600}}")
        lay=QHBoxLayout(self); lay.setContentsMargins(9,5,9,5); lay.setSpacing(4)
        label=QLabel(text); label.setWordWrap(True); label.setAlignment(Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft); lay.addWidget(label)
        self.setToolTip(tooltip); self.setMinimumHeight(34); self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton: self.clicked.emit()
        super().mousePressEvent(event)

class TaskDialog(QDialog):
    def __init__(self,parent,task=None,categories=None,default_category=None):
        super().__init__(parent); self.setWindowTitle("할 일 편집" if task else "할 일 추가"); self.setMinimumWidth(590)
        self.t=json.loads(json.dumps(task or newtask())); self.cats=categories or CATS
        if task is None and default_category and any(c.get("name")==default_category for c in self.cats):
            self.t["category"]=default_category
        outer=QVBoxLayout(self); form=QFormLayout(); outer.addLayout(form)
        self.title=QLineEdit(self.t.get("title","")); self.title.setPlaceholderText("할 일을 입력하세요")
        self.cat=QComboBox()
        for c in self.cats:self.cat.addItem(c["emoji"]+" "+c["name"],c["name"])
        ix=self.cat.findData(self.t.get("category","일상")); self.cat.setCurrentIndex(max(ix,0))
        self.pri=QComboBox(); self.pri.addItems(["높음","보통","낮음"]); self.pri.setCurrentText(self.t.get("priority","보통"))
        form.addRow("할 일",self.title); form.addRow("카테고리",self.cat); form.addRow("우선순위",self.pri)

        today=QDate.currentDate()
        self.date_toggle=QCheckBox("날짜 지정 사용")
        self.date_toggle.setChecked(bool(self.t.get("date_enabled",False)))
        form.addRow(self.date_toggle)
        self.date_group=QWidget(); dg=QFormLayout(self.date_group); dg.setContentsMargins(12,0,0,0)
        self.sd=QDateEdit(calendarPopup=True); self.sd.setDisplayFormat("yyyy-MM-dd"); self.sd.setDate(today)
        sd=self.t.get("start_date",""); x=QDate.fromString(sd[:10],"yyyy-MM-dd") if sd else QDate(); self.sd.setDate(x if x.isValid() else today)
        self.d=QDateEdit(calendarPopup=True); self.d.setDisplayFormat("yyyy-MM-dd"); self.d.setDate(today)
        due=self.t.get("due",""); x=QDate.fromString(due[:10],"yyyy-MM-dd") if due else QDate(); self.d.setDate(x if x.isValid() else today)
        self.all_day=QCheckBox("하루 종일"); self.all_day.setChecked(not (len(due)>10))
        self.tm=QTimeEdit(); self.tm.setDisplayFormat("HH:mm")
        if due and len(due)>10:
            qtime=QTime.fromString(due[11:16],"HH:mm")
            if qtime.isValid():self.tm.setTime(qtime)
        self.calendar_visible=QCheckBox("달력에 표시"); self.calendar_visible.setChecked(bool(self.t.get("show_in_calendar",False)))
        dg.addRow("시작일",self.sd); dg.addRow("마감일",self.d); dg.addRow("",self.all_day); dg.addRow("마감 시간",self.tm); dg.addRow("",self.calendar_visible)
        form.addRow(self.date_group); self.date_toggle.toggled.connect(self.date_group.setVisible); self.date_toggle.toggled.connect(self.update_time_enabled)

        rep=self.t.get("repeat",{}); self.repeat_toggle=QCheckBox("반복 설정 사용"); self.repeat_toggle.setChecked(rep.get("type","없음")!="없음")
        form.addRow(self.repeat_toggle)
        self.repeat_group=QWidget(); rg=QFormLayout(self.repeat_group); rg.setContentsMargins(12,0,0,0)
        self.rep=QComboBox(); self.rep.addItems(["없음","매일","매주","매월"]); self.rep.setCurrentText(rep.get("type","없음"))
        days=QWidget(); dl=QHBoxLayout(days); dl.setContentsMargins(0,0,0,0); self.days={}
        for i,day in enumerate(["월","화","수","목","금","토","일"]):
            cb=QCheckBox(day); cb.setStyleSheet("QCheckBox{font-size:17pt;font-weight:bold;padding:5px} QCheckBox:disabled{color:#9aa0aa}"); cb.setChecked(i in rep.get("weekdays",[])); self.days[i]=cb; dl.addWidget(cb)
        self.md=QSpinBox(); self.md.setRange(1,31); self.md.setValue(int(rep.get("monthday",1)))
        self.rt=QTimeEdit(); self.rt.setDisplayFormat("HH:mm"); qt=QTime.fromString(rep.get("time","09:00"),"HH:mm"); self.rt.setTime(qt if qt.isValid() else QTime(9,0))
        self.rt_none=QCheckBox("시간 없음"); self.rt_none.setChecked(bool(rep.get("time_none",False)))
        self.repeat_summary=QLabel(); self.repeat_summary.setStyleSheet("font-weight:bold;font-size:13pt;padding:5px")
        rg.addRow("반복 방식",self.rep); rg.addRow("반복 요일",days); rg.addRow("매월 반복 일자",self.md); rg.addRow("반복 시간",self.rt); rg.addRow("",self.rt_none); rg.addRow("반복 내용",self.repeat_summary)
        form.addRow(self.repeat_group); self.repeat_toggle.toggled.connect(self.repeat_group.setVisible); self.repeat_toggle.toggled.connect(self.update_repeat_enabled)

        self.reminder_toggle=QCheckBox("알림 설정 사용")
        self.reminder_toggle.setChecked(bool(self.t.get("reminder","")))
        form.addRow(self.reminder_toggle)
        self.reminder_group=QWidget(); ag=QFormLayout(self.reminder_group); ag.setContentsMargins(12,0,0,0)
        rmmap={"":"알림 없음","due":"마감 시간에 알림","startup":"PC 켜질 때 알림","morning":"PC 켜질 때 알림","custom":"사용자 지정 시간","due_before_5":"마감 5분 전","due_before_10":"마감 10분 전","due_before_30":"마감 30분 전","due_before_60":"마감 1시간 전"}
        self.rem=QComboBox(); self.rem.addItems(["알림 없음","마감 시간에 알림","마감 5분 전","마감 10분 전","마감 30분 전","마감 1시간 전","PC 켜질 때 알림","사용자 지정 시간"]); self.rem.setCurrentText(rmmap.get(self.t.get("reminder",""),"알림 없음"))
        self.rd=QDateEdit(calendarPopup=True); self.rd.setDisplayFormat("yyyy-MM-dd"); self.rd.setDate(today); self.rtm=QTimeEdit(); self.rtm.setDisplayFormat("HH:mm"); self.rtm.setTime(QTime.currentTime())
        try:
            z=datetime.strptime(self.t.get("reminder_at",""),"%Y-%m-%d %H:%M"); self.rd.setDate(QDate(z.year,z.month,z.day)); self.rtm.setTime(QTime(z.hour,z.minute))
        except: pass
        self.rem_interval=QSpinBox(); self.rem_interval.setRange(1,10080); self.rem_interval.setValue(int(self.t.get("reminder_interval",5) or 5))
        self.rem_unit=QComboBox(); self.rem_unit.addItems(["분","시간"]); self.rem_unit.setCurrentText(self.t.get("reminder_interval_unit","분"))
        self.rem_count=QSpinBox(); self.rem_count.setRange(1,999); self.rem_count.setValue(int(self.t.get("reminder_count",3) or 3))
        ag.addRow("알림 방식",self.rem); ag.addRow("사용자 지정 날짜",self.rd); ag.addRow("사용자 지정 시간",self.rtm)
        intervalrow=QWidget(); il=QHBoxLayout(intervalrow); il.setContentsMargins(0,0,0,0); il.addWidget(self.rem_interval); il.addWidget(self.rem_unit); il.addWidget(QLabel("반복 횟수")); il.addWidget(self.rem_count); ag.addRow("알림 반복",intervalrow)
        form.addRow(self.reminder_group); self.reminder_toggle.toggled.connect(self.reminder_group.setVisible); self.reminder_toggle.toggled.connect(self.update_reminder_enabled)

        self.d.dateChanged.connect(self.update_time_enabled); self.all_day.toggled.connect(self.update_time_enabled); self.rem.currentTextChanged.connect(self.update_reminder_enabled); self.rep.currentTextChanged.connect(self.update_repeat_enabled); self.rt_none.toggled.connect(self.update_repeat_enabled)
        for cb in self.days.values():cb.toggled.connect(self.update_repeat_summary)
        self.md.valueChanged.connect(self.update_repeat_summary); self.rt.timeChanged.connect(self.update_repeat_summary); self.rt_none.toggled.connect(self.update_repeat_summary)
        self.date_group.setVisible(self.date_toggle.isChecked()); self.repeat_group.setVisible(self.repeat_toggle.isChecked()); self.reminder_group.setVisible(self.reminder_toggle.isChecked())
        self.update_time_enabled(); self.update_reminder_enabled(); self.update_repeat_enabled(); self.update_repeat_summary()
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); outer.addWidget(buttons)
    def update_time_enabled(self): self.tm.setEnabled(self.date_toggle.isChecked() and not self.all_day.isChecked())
    def update_reminder_enabled(self):
        mode=self.rem.currentText(); custom=mode=="사용자 지정 시간"; enabled=self.reminder_toggle.isChecked() and mode!="알림 없음"
        self.rd.setEnabled(enabled and custom); self.rtm.setEnabled(enabled and custom)
        for w in (self.rem_interval,self.rem_unit,self.rem_count):w.setEnabled(enabled)
    def update_repeat_enabled(self):
        typ=self.rep.currentText() if self.repeat_toggle.isChecked() else "없음"
        for i,w in self.days.items():w.setEnabled(typ=="매주")
        self.md.setEnabled(typ=="매월")
        self.rt.setEnabled(typ!="없음" and not self.rt_none.isChecked())
        self.rt_none.setEnabled(typ!="없음")
        self.update_repeat_summary()
    def update_repeat_summary(self):
        typ=self.rep.currentText() if self.repeat_toggle.isChecked() else "없음"; tm="시간 없음" if self.rt_none.isChecked() else self.rt.time().toString("HH:mm")
        if typ=="없음":txt="반복 없음"
        elif typ=="매일":txt=f"매일 · {tm}"
        elif typ=="매주":
            ds=" · ".join(["월화수목금토일"[i] for i,c in self.days.items() if c.isChecked()]) or "요일 미선택"; txt=f"매주  {ds}요일  ·  {tm}"
        else:txt=f"매월  {self.md.value()}일  ·  {tm}"
        self.repeat_summary.setText(txt)
    def accept(self):
        title=self.title.text().strip()
        if not title: QMessageBox.warning(self,"확인","할 일 내용을 입력해 주세요."); return
        if self.repeat_toggle.isChecked() and self.rep.currentText()=="매주" and not any(c.isChecked() for c in self.days.values()):
            QMessageBox.warning(self,"반복 설정","매주 반복은 요일을 하나 이상 선택해 주세요."); return
        t=self.t; t["title"]=title; t["category"]=self.cat.currentData(); t["priority"]=self.pri.currentText()
        if self.date_toggle.isChecked() and self.sd.date()>self.d.date():
            QMessageBox.warning(self,"날짜 확인","시작일은 마감일보다 늦을 수 없습니다."); return
        today=QDate.currentDate().toString("yyyy-MM-dd")
        t["date_enabled"]=self.date_toggle.isChecked()
        t["start_date"]=self.sd.date().toString("yyyy-MM-dd") if self.date_toggle.isChecked() else today
        t["due"]=self.d.date().toString("yyyy-MM-dd")+ (" "+self.tm.time().toString("HH:mm") if self.date_toggle.isChecked() and not self.all_day.isChecked() else "") if self.date_toggle.isChecked() else today
        t["show_in_calendar"]=self.date_toggle.isChecked() and self.calendar_visible.isChecked()
        typ=self.rep.currentText() if self.repeat_toggle.isChecked() else "없음"
        t["repeat"]={"type":typ,"weekdays":[i for i,c in self.days.items() if c.isChecked() ],"monthday":self.md.value(),"time":self.rt.time().toString("HH:mm"),"time_none":self.rt_none.isChecked()}
        mode=self.rem.currentText() if self.reminder_toggle.isChecked() else "알림 없음"
        rmap={"알림 없음":"","마감 시간에 알림":"due","마감 5분 전":"due_before_5","마감 10분 전":"due_before_10","마감 30분 전":"due_before_30","마감 1시간 전":"due_before_60","PC 켜질 때 알림":"startup","사용자 지정 시간":"custom"}
        t["reminder"]=rmap[mode]
        t["reminder_at"]=self.rd.date().toString("yyyy-MM-dd")+" "+self.rtm.time().toString("HH:mm") if mode=="사용자 지정 시간" else ""
        if mode=="알림 없음":t["reminder_interval"]=0; t["reminder_count"]=0
        else:t["reminder_interval"]=self.rem_interval.value(); t["reminder_interval_unit"]=self.rem_unit.currentText(); t["reminder_count"]=self.rem_count.value()
        super().accept()

class CategoryDialog(QDialog):
    EMOJIS = ["🌿","💼","📚","🎨","💪","🏠","💰","🛒","❤️","⭐","🎮","✈️","🍀","📝","🎵","📌","🧹","🐾","☕","🎁","💡","📷","🌈","🧘"]
    def __init__(self,parent,categories):
        super().__init__(parent); self.setWindowTitle("카테고리 추가"); self.setMinimumWidth(360)
        self.chosen_emoji="📌"; self.chosen_color="#8aa4d6"
        layout=QVBoxLayout(self); form=QFormLayout()
        self.name=QLineEdit(); self.name.setPlaceholderText("예: 자기계발")
        form.addRow("카테고리 이름",self.name); layout.addLayout(form)
        layout.addWidget(QLabel("이모지 선택"))
        grid=QGridLayout()
        for i,emoji in enumerate(self.EMOJIS):
            b=QPushButton(emoji); b.setFixedSize(44,40); b.setStyleSheet("font-size:18px")
            b.clicked.connect(lambda _,e=emoji:self.pick_emoji(e))
            grid.addWidget(b,i//6,i%6)
        layout.addLayout(grid)
        self.emoji_label=QLabel("선택한 이모지: 📌"); layout.addWidget(self.emoji_label); self.emoji_input=QLineEdit("📌"); self.emoji_input.setPlaceholderText("원하는 이모지를 붙여넣거나 입력하세요"); self.emoji_input.textChanged.connect(self.emoji_typed); layout.addWidget(self.emoji_input)
        colorrow=QHBoxLayout(); self.colorpreview=QLabel("      "); self.colorpreview.setStyleSheet("background:#8aa4d6;border-radius:6px"); self.colorpreview.setFixedSize(42,26)
        colorrow.addWidget(self.colorpreview); self.colorbtn=QPushButton("카테고리 색상 선택…"); self.colorbtn.clicked.connect(self.pick_color); colorrow.addWidget(self.colorbtn); colorrow.addStretch(); layout.addLayout(colorrow)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def pick_emoji(self,e):
        self.chosen_emoji=e; self.emoji_input.setText(e); self.emoji_label.setText("선택한 이모지: "+e)
    def emoji_typed(self,e):
        if e.strip():self.chosen_emoji=e.strip(); self.emoji_label.setText("선택한 이모지: "+self.chosen_emoji)
    def pick_color(self):
        c=QColorDialog.getColor(QColor(self.chosen_color),self,"카테고리 색상 선택")
        if c.isValid():
            self.chosen_color=c.name(QColor.NameFormat.HexRgb)
            self.colorpreview.setStyleSheet(f"background:{self.chosen_color};border-radius:6px")
    def result_category(self):
        return {"name":self.name.text().strip(),"emoji":self.chosen_emoji,"color":QColor(self.chosen_color).name(QColor.NameFormat.HexRgb)}


class CalendarWidget(QCalendarWidget):
    """Calendar with compact date labels and non-overlapping category strips across task ranges."""
    def __init__(self,parent=None):
        super().__init__(parent); self.day_entries={}; self.holiday_dates=set()
    def set_day_entries(self,entries):
        self.day_entries=entries or {}; self.updateCells()
    def set_holidays(self,dates):
        self.holiday_dates=set(dates or []); self.updateCells()
    def paintCell(self,painter,rect,qdate):
        super().paintCell(painter,rect,qdate)
        painter.save(); key=qdate.toString("yyyy-MM-dd")
        # Cover Qt's centered day number with a compact top-left date label.
        bg=self.palette().color(QPalette.ColorRole.Base)
        if qdate==self.selectedDate(): bg=self.palette().color(QPalette.ColorRole.Highlight).lighter(175)
        painter.fillRect(rect.adjusted(1,1,-1,-rect.height()+18),bg)
        if key in self.holiday_dates or qdate.dayOfWeek()==7: daycolor=QColor("#d93645")
        elif qdate.dayOfWeek()==6: daycolor=QColor("#2878d0")
        else: daycolor=self.palette().color(QPalette.ColorRole.Text)
        painter.setPen(daycolor); painter.setFont(QFont(QApplication.instance().font().family(),7,QFont.Weight.Bold))
        painter.drawText(rect.adjusted(3,1,-2,-rect.height()+17),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop,str(qdate.day()))
        entries=self.day_entries.get(key,[])
        if entries:
            top=rect.top()+19; bottom=rect.bottom()-2; lane_h=12; maxlanes=max(0,(bottom-top+1)//lane_h)
            shown=entries[:maxlanes]
            for i,e in enumerate(shown):
                y=top+i*lane_h; color=QColor(e.get("color","#8aa4d6")); painter.fillRect(rect.left()+1,y,rect.width()-2,lane_h-1,color)
                painter.setPen(QColor("#202435")); painter.setFont(QFont(QApplication.instance().font().family(),6))
                label=e.get("title","")
                if e.get("start") and key==e.get("start"): label="▶ "+label
                elif e.get("due") and key==e.get("due"): label=label+" ◀"
                painter.drawText(rect.left()+4,y,rect.width()-7,lane_h-1,Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,painter.fontMetrics().elidedText(label,Qt.TextElideMode.ElideRight,max(1,rect.width()-9)))
            if len(entries)>len(shown) and maxlanes:
                y=top+(maxlanes-1)*lane_h; painter.fillRect(rect.left()+1,y,rect.width()-2,lane_h-1,QColor("#e5e7eb")); painter.setPen(QColor("#333333")); painter.drawText(rect.left()+4,y,rect.width()-7,lane_h-1,Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,f"+{len(entries)-len(shown)+1} more")
        painter.restore()


class App(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(APP); self.resize(1160,760); self.setMinimumSize(900,600)
        os.makedirs(DATA_DIR,exist_ok=True); self.tasks=[]; self.cats=CATS.copy(); self.catfilter="전체"; 
        self.calendar_view_default="Monthly"; self.load(); self.ui(); self.theme(); self.refresh(); self.check_alerts(True)
        self.timer=QTimer(self); self.timer.timeout.connect(self.check_alerts); self.timer.start(30000)
    def load(self):
        if not os.path.exists(DATA_FILE):return
        try:
            data=json.load(open(DATA_FILE,encoding="utf-8")); self.cats=data.get("categories",CATS); self.calendar_view_default=data.get("calendar_view_default","Monthly")
            if self.cats and isinstance(self.cats[0],str):self.cats=[{"name":x,"emoji":"📌","color":"#8aa4d6"} for x in self.cats]
            for old in data.get("tasks",[]):
                t=newtask(); t.update(old)
                if isinstance(t.get("repeat"),str):t["repeat"]={"type":t["repeat"] if t["repeat"] in ["매일","매주","매월"] else "없음","weekdays":[],"monthday":1,"time":"09:00"}
                if not isinstance(t.get("repeat"),dict):t["repeat"]=newtask()["repeat"]
                for k,v in [("subtasks",[]),("history",[]),("reminded",[]),("reminder",""),("reminder_at",""),("reminder_interval",5),("reminder_interval_unit","분"),("reminder_count",3)]:t.setdefault(k,v)
                if not t.get("start_date"):t["start_date"]=date.today().isoformat()
                if not t.get("due"):t["due"]=date.today().isoformat()
                t.setdefault("date_enabled",False); t.setdefault("show_in_calendar",False)
                self.tasks.append(t)
        except Exception as e:QMessageBox.warning(self,"저장 파일",str(e))
    def save(self):
        os.makedirs(DATA_DIR,exist_ok=True); tmp=DATA_FILE+".tmp"
        with open(tmp,"w",encoding="utf-8") as f:json.dump({"tasks":self.tasks,"categories":self.cats,"calendar_view_default":getattr(self,"calendar_view_default","Monthly")},f,ensure_ascii=False,indent=2)
        os.replace(tmp,DATA_FILE)
    def ui(self):
        central=QWidget(); self.setCentralWidget(central); root=QHBoxLayout(central); root.setContentsMargins(0,0,0,0)
        self.side=QFrame(); self.side.setFixedWidth(300); self.side.setMinimumWidth(300); self.side.setObjectName("side"); s=QVBoxLayout(self.side)
        brand=QLabel("BEST CHECKLIST"); brand.setObjectName("brand"); brand.setMinimumWidth(260); brand.setWordWrap(False); s.addWidget(brand); s.addWidget(QLabel("MY CHECKLIST INDEX")); self.collapsebtn=QPushButton("◀ 사이드바 접기"); self.collapsebtn.clicked.connect(self.toggle_sidebar); s.addWidget(self.collapsebtn)
        navrow=QHBoxLayout(); self.homebtn=QPushButton("⌂"); self.homebtn.setToolTip("홈"); self.homebtn.setStyleSheet("font-size:18pt"); self.homebtn.clicked.connect(lambda:self.page("홈")); self.calbtn=QPushButton("▦"); self.calbtn.setToolTip("달력"); self.calbtn.setStyleSheet("font-size:18pt"); self.calbtn.clicked.connect(lambda:self.page("달력")); navrow.addWidget(self.homebtn); navrow.addWidget(self.calbtn); s.addLayout(navrow)
        s.addSpacing(12); hr=QHBoxLayout(); hr.addWidget(QLabel("CATEGORY INDEX")); plus=QPushButton("+"); plus.clicked.connect(self.addcat); hr.addWidget(plus); s.addLayout(hr)
        self.catsbox=QVBoxLayout(); s.addLayout(self.catsbox); s.addStretch(); self.side_widgets=[brand,self.collapsebtn]
        exp=QPushButton("백업 내보내기"); exp.clicked.connect(self.backup); s.addWidget(exp)
        imp=QPushButton("백업 가져오기"); imp.clicked.connect(self.import_backup); s.addWidget(imp); root.addWidget(self.side)
        main=QWidget(); m=QVBoxLayout(main); m.setContentsMargins(26,22,26,22)
        top=QHBoxLayout(); self.pagetitle=QLabel("Today · Checklist"); self.pagetitle.setObjectName("title"); top.addWidget(self.pagetitle); top.addStretch()
        self.search=QLineEdit(); self.search.setPlaceholderText("⌕ 검색"); self.search.textChanged.connect(self.refresh_tasks); self.search.setMaximumWidth(190); top.addWidget(self.search)
        add=QPushButton("+ 할 일 추가"); add.setObjectName("primary"); add.clicked.connect(self.addtask); top.addWidget(add); m.addLayout(top)
        self.stack=QStackedWidget(); m.addWidget(self.stack,1); root.addWidget(main,1)
        home=QWidget(); h=QVBoxLayout(home); self.welcome=QLabel("작은 체크가 모여 오늘을 완성해요 ✨"); h.addWidget(self.welcome)
        card=QFrame(); card.setObjectName("card"); cv=QVBoxLayout(card); h.addWidget(card)
        filters=QHBoxLayout(); self.status=QComboBox(); self.status.addItems(["전체 상태","미완료","완료"]); self.status.currentIndexChanged.connect(self.refresh_tasks); filters.addWidget(self.status)
        self.priority=QComboBox(); self.priority.addItems(["모든 우선순위","높음","보통","낮음"]); self.priority.currentIndexChanged.connect(self.refresh_tasks); filters.addWidget(self.priority)
        self.sort=QComboBox(); self.sort.addItems(["수동 순서","마감일 순","우선순위 순","카테고리 순","최근 추가 순"]); self.sort.currentIndexChanged.connect(self.refresh_tasks); filters.addWidget(self.sort); filters.addStretch(); h.addLayout(filters)
        self.list=QListWidget(); self.list.setDragDropMode(QListWidget.InternalMove); self.list.setSpacing(5); self.list.model().rowsMoved.connect(self.reorder); self.list.currentItemChanged.connect(self.show_subtasks); h.addWidget(self.list,1)
        subbox=QFrame(); subbox.setObjectName("card"); sv=QVBoxLayout(subbox); self.subhead=QLabel("Subtasks · 할 일을 선택하세요"); self.subhead.setStyleSheet("font-weight:bold"); sv.addWidget(self.subhead); self.subitems=QVBoxLayout(); sv.addLayout(self.subitems); subrow=QHBoxLayout(); self.subinput=QLineEdit(); self.subinput.setPlaceholderText("하위 할 일 입력 후 Enter"); self.subinput.returnPressed.connect(self.add_subtask); self.subadd=QPushButton("추가"); self.subadd.clicked.connect(self.add_subtask); subrow.addWidget(self.subinput,1); subrow.addWidget(self.subadd); sv.addLayout(subrow); h.addWidget(subbox); self.stack.addWidget(home)
        cal=QWidget(); cv=QVBoxLayout(cal); cv.setContentsMargins(0,0,0,0)
        caltoolbar=QHBoxLayout(); caltoolbar.addWidget(QLabel("보기")); self.calendar_mode=QComboBox(); self.calendar_mode.addItems(["Monthly","WEEKLY"]); self.calendar_mode.currentTextChanged.connect(self.set_calendar_mode); caltoolbar.addWidget(self.calendar_mode)
        caltoolbar.addSpacing(12); caltoolbar.addWidget(QLabel("기본 보기")); self.calendar_default=QComboBox(); self.calendar_default.addItems(["Monthly","WEEKLY"]); self.calendar_default.setCurrentText(getattr(self,"calendar_view_default","Monthly")); self.calendar_default.currentTextChanged.connect(self.set_calendar_default); caltoolbar.addWidget(self.calendar_default); caltoolbar.addStretch(); cv.addLayout(caltoolbar)
        cr=QHBoxLayout(); self.calendar_views=QStackedWidget(); monthly=QWidget(); ml=QVBoxLayout(monthly); self.calendar=CalendarWidget(); self.calendar.setGridVisible(True); self.calendar.setMinimumWidth(300); self.calendar.setMaximumWidth(390); self.calendar.setStyleSheet("QCalendarWidget QTableView {font-size: 8pt;}"); self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader); self.calendar.setNavigationBarVisible(True); self.calendar.selectionChanged.connect(self.refresh_calendar); self.calendar.clicked.connect(self.add_for_date); ml.addWidget(self.calendar); self.calendar_views.addWidget(monthly)
        weekly=QWidget(); wl=QVBoxLayout(weekly); weeknav=QHBoxLayout(); self.weekprev=QPushButton("◀ 이전 주"); self.weekprev.clicked.connect(lambda:self.shift_week(-7)); self.weeklabel=QLabel(); self.weeklabel.setAlignment(Qt.AlignmentFlag.AlignCenter); self.weeknext=QPushButton("다음 주 ▶"); self.weeknext.clicked.connect(lambda:self.shift_week(7)); weeknav.addWidget(self.weekprev); weeknav.addWidget(self.weeklabel,1); weeknav.addWidget(self.weeknext); wl.addLayout(weeknav); self.weekgrid=QGridLayout(); self.weekgrid.setSpacing(3); self.weekgrid.setContentsMargins(3,3,3,3); wl.addLayout(self.weekgrid,1); self.calendar_views.addWidget(weekly); cr.addWidget(self.calendar_views,1)
        self.calendar_right_panel=QWidget(); rr=QVBoxLayout(self.calendar_right_panel); self.calhead=QLabel("선택한 날짜"); self.calitems=QListWidget(); rr.addWidget(self.calhead); rr.addWidget(self.calitems,1); b=QPushButton("선택한 날짜에 할 일 추가"); b.clicked.connect(self.add_for_date); rr.addWidget(b); cr.addWidget(self.calendar_right_panel,0); cv.addLayout(cr,1); self.stack.addWidget(cal)
        self.calendar_mode.setCurrentText(getattr(self,"calendar_view_default","Monthly")); self.calendar_default.setCurrentText(getattr(self,"calendar_view_default","Monthly")); self.set_calendar_mode(self.calendar_mode.currentText())
        self.page("홈")
    def toggle_sidebar(self):
        collapsed=self.side.width()>100
        if collapsed:
            self.side.setFixedWidth(66); self.side.setMinimumWidth(66); self.collapsebtn.setText("▶"); self.collapsebtn.setToolTip("사이드바 펼치기"); self.side_collapsed=True
            for w in self.side.findChildren(QWidget):
                if w is not self.collapsebtn:w.hide()
        else:
            self.side.setFixedWidth(300); self.side.setMinimumWidth(300); self.collapsebtn.setText("◀ 사이드바 접기"); self.side_collapsed=False
            for w in self.side.findChildren(QWidget):w.show()
            self.refresh_cats()
        self.side_collapsed=collapsed
    def theme(self):
        bg,panel,fg,muted,border,accent,side="#f7f8fc","#ffffff","#282d3a","#858da0","#e7e9f1","#607fce","#ffffff"
        QApplication.instance().setFont(QFont("Malgun Gothic",10))
        QApplication.instance().setStyleSheet(f"""QWidget{{background:{bg};color:{fg};font-family:'Malgun Gothic';font-size:10pt}}#side{{background:{side};border-right:1px solid {border}}}#brand{{font-size:21pt;font-weight:bold;color:{accent}}}#title{{font-size:22pt;font-weight:bold}}#card{{background:{panel};border:1px solid {border};border-radius:14px;padding:10px}}QPushButton{{background:{panel};border:1px solid {border};border-radius:8px;padding:8px}}QPushButton#primary{{background:{accent};color:white}}QLineEdit,QComboBox,QDateEdit,QTimeEdit,QSpinBox,QTextEdit{{background:{panel};border:1px solid {border};border-radius:7px;padding:7px}}QListWidget{{background:transparent;border:0}}QListWidget::item{{border:0}}QCalendarWidget QWidget{{background:{panel};color:{fg}}}QWidget:disabled{{color:{muted};background:#f0f1f4}}""")
    def page(self,name):
        ix={"홈":0,"달력":1}.get(name,0); self.stack.setCurrentIndex(ix); self.pagetitle.setText({"홈":"Checklist","달력":"Calendar"}.get(name,"Checklist"))
        if name=="달력":self.refresh_calendar()
    def addcat(self):
        dlg=CategoryDialog(self,self.cats)
        if dlg.exec()!=QDialog.Accepted:return
        cat=dlg.result_category()
        if not cat["name"]:QMessageBox.information(self,"카테고리","카테고리 이름을 입력해 주세요."); return
        if any(c["name"]==cat["name"] for c in self.cats):QMessageBox.information(self,"카테고리","같은 이름의 카테고리가 이미 있어요."); return
        self.cats.append(cat); self.save(); self.refresh_cats()
    def editcat(self, old_name):
        cat=next((c for c in self.cats if c["name"]==old_name),None)
        if not cat:return
        dlg=CategoryDialog(self,self.cats)
        dlg.setWindowTitle("카테고리 수정")
        dlg.name.setText(cat["name"]); dlg.chosen_emoji=cat.get("emoji","📌")
        dlg.emoji_label.setText("선택한 이모지: "+dlg.chosen_emoji); dlg.emoji_input.setText(dlg.chosen_emoji)
        dlg.chosen_color=cat.get("color","#8aa4d6")
        dlg.colorpreview.setStyleSheet(f"background:{dlg.chosen_color};border-radius:6px")
        if dlg.exec()!=QDialog.Accepted:return
        updated=dlg.result_category()
        if not updated["name"]:QMessageBox.information(self,"카테고리","카테고리 이름을 입력해 주세요."); return
        if any(c["name"]==updated["name"] and c["name"]!=old_name for c in self.cats):QMessageBox.information(self,"카테고리","같은 이름의 카테고리가 이미 있어요."); return
        cat.update(updated)
        if old_name!=updated["name"]:
            for task in self.tasks:
                if task.get("category")==old_name:task["category"]=updated["name"]
            if self.catfilter==old_name:self.catfilter=updated["name"]
        self.save(); self.refresh()
    def deletecat(self, name):
        if len(self.cats)<=1:
            QMessageBox.information(self,"카테고리 삭제","카테고리는 최소 1개 이상 있어야 합니다."); return
        destinations=[c["name"] for c in self.cats if c["name"]!=name]
        used=any(t.get("category")==name for t in self.tasks)
        target=destinations[0]
        if used:
            target,ok=QInputDialog.getItem(self,"카테고리 삭제",f"'{name}' 카테고리의 할 일을 어디로 옮길까요?",destinations,0,False)
            if not ok:return
        answer=QMessageBox.question(self,"카테고리 삭제",f"'{name}' 카테고리를 삭제할까요?"+(f"\n포함된 할 일은 '{target}'로 이동합니다." if used else ""),QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes:return
        if used:
            for task in self.tasks:
                if task.get("category")==name:task["category"]=target
        self.cats=[c for c in self.cats if c["name"]!=name]
        if self.catfilter==name:self.catfilter="전체"
        self.save(); self.refresh()
    def refresh_cats(self):
        while self.catsbox.count():
            x=self.catsbox.takeAt(0)
            if x.widget():x.widget().deleteLater()
        b=QPushButton("⌕ 전체 보기"); b.clicked.connect(lambda:self.setcat("전체")); self.catsbox.addWidget(b)
        for c in self.cats:
            row=QWidget(); lay=QHBoxLayout(row); lay.setContentsMargins(0,0,0,0); lay.setSpacing(3)
            b=QPushButton(c["emoji"]+"  "+c["name"]); b.setToolTip(c["name"]); b.setMinimumWidth(90)
            active=(self.catfilter==c["name"]); color=c.get("color","#8aa4d6")
            b.setStyleSheet(f"text-align:left;font-weight:{'bold' if active else 'normal'};background:{color};color:#202435;border:1px solid {color}")
            b.clicked.connect(lambda _,n=c["name"]:self.setcat(n)); lay.addWidget(b,1)
            e=QPushButton("✎"); e.setFixedWidth(30); e.setToolTip("카테고리 수정"); e.clicked.connect(lambda _,n=c["name"]:self.editcat(n)); lay.addWidget(e)
            d=QPushButton("×"); d.setFixedWidth(30); d.setToolTip("카테고리 삭제"); d.clicked.connect(lambda _,n=c["name"]:self.deletecat(n)); lay.addWidget(d)
            self.catsbox.addWidget(row)
    def setcat(self,n):self.catfilter=n; self.page("홈"); self.refresh_tasks()
    def addtask(self):self.edit_task(None)
    def add_for_date(self, qdate=None):
        t=newtask(); selected=(qdate if qdate is not None else self.calendar.selectedDate()).toString("yyyy-MM-dd"); t["start_date"]=selected; t["due"]=selected; t["date_enabled"]=True; self.edit_task(t,True)
    def edit_task(self,t,isnew=False):
        creating = (t is None) or isnew
        dlg=TaskDialog(self,t,self.cats,default_category=(self.catfilter if self.catfilter!="전체" else None))
        if dlg.exec()!=QDialog.Accepted:return
        obj=dlg.t
        if isnew or not any(x["id"]==obj.get("id") for x in self.tasks):
            obj["id"]=str(uuid.uuid4()); obj["created"]=stamp(); obj["order"]=len(self.tasks); self.tasks.append(obj)
        else:
            for i,x in enumerate(self.tasks):
                if x["id"]==obj["id"]:self.tasks[i]=obj; break
        if creating:
            self.catfilter=obj.get("category","전체")
            self.search.clear()
            self.status.setCurrentIndex(0)
        self.save(); self.refresh()
    def filtered(self):
        q=self.search.text().lower().strip(); out=[]
        for t in self.tasks:
            if self.catfilter!="전체" and t.get("category")!=self.catfilter:continue
            if q and q not in t.get("title","").lower() and not any(q in sub.get("title","").lower() for sub in t.get("subtasks",[])):continue
            if self.status.currentText()=="미완료" and t.get("done"):continue
            if self.status.currentText()=="완료" and not t.get("done"):continue
            if self.priority.currentText()!="모든 우선순위" and t.get("priority","보통")!=self.priority.currentText():continue
            out.append(t)
        mode=self.sort.currentText()
        if mode=="마감일 순":out.sort(key=lambda x:x.get("due") or "9999")
        elif mode=="우선순위 순":out.sort(key=lambda x:{"높음":0,"보통":1,"낮음":2}.get(x.get("priority","보통"),1))
        elif mode=="카테고리 순":out.sort(key=lambda x:x.get("category",""))
        elif mode=="최근 추가 순":out.sort(key=lambda x:x.get("created",""),reverse=True)
        else:out.sort(key=lambda x:x.get("order",0))
        return sorted(out,key=lambda x:bool(x.get("done")))
    def refresh_tasks(self):
        if not hasattr(self,"list"):return
        keep_id=getattr(self,"selected_task_id",None)
        self.list.clear(); today=date.today().isoformat()
        for t in self.filtered():
            it=QListWidgetItem(); it.setData(Qt.UserRole,t["id"]); cardrow=QWidget(); outer=QVBoxLayout(cardrow); outer.setContentsMargins(6,5,6,5); outer.setSpacing(3); row=QWidget(); l=QHBoxLayout(row); l.setContentsMargins(10,8,10,8)
            cb=QPushButton("✓" if t.get("done",False) else ""); cb.setCheckable(True); cb.setChecked(t.get("done",False)); cb.setFixedSize(28,28); cb.setStyleSheet("QPushButton{border:2px solid #8c96a8;border-radius:14px;padding:0;font-weight:bold;font-size:15pt;background:#6f8fe0;color:white}" if t.get("done",False) else "QPushButton{border:2px solid #8c96a8;border-radius:14px;padding:0;background:transparent}"); cb.clicked.connect(lambda checked,tid=t["id"]:self.toggle(tid,checked)); l.addWidget(cb)
            title=ClickLabel(t.get("title","")); title.setWordWrap(True); title.setCursor(Qt.PointingHandCursor); title.clicked.connect(lambda tid=t["id"]:self.select_task(tid))
            if t.get("done"):title.setStyleSheet("text-decoration:line-through;color:#9299a8")
            l.addWidget(title,1); c=next((c for c in self.cats if c["name"]==t.get("category")),{"emoji":"📌","name":t.get("category","")})
            catlabel=QLabel(c["emoji"]+" "+c["name"]); catlabel.setStyleSheet("font-weight:bold"); l.addWidget(catlabel); row.setStyleSheet(f"background:{c.get('color','#8aa4d6')};border-radius:10px; QLabel{{background:transparent;color:#202435}}") ; l.addWidget(QLabel({"높음":"🔴 높음","보통":"🟡 보통","낮음":"🟢 낮음"}.get(t.get("priority","보통"))))
            due=t.get("due",""); start=t.get("start_date","")
            def date_label(value):
                try:
                    dd=date.fromisoformat(value[:10]); return f"{dd.month}/{dd.day}({['월','화','수','목','금','토','일'][dd.weekday()]})"
                except Exception: return ""
            sdlabel=date_label(start); dulabel=date_label(due)
            if sdlabel and dulabel and sdlabel!=dulabel: date_text=f"{sdlabel} ~ {dulabel}"
            else: date_text=dulabel or sdlabel or ""
            if due and len(due)>10: date_text += " " + due[11:16]
            elif due: date_text += " · 종일"
            dl=QLabel(date_text if date_text.strip() else "날짜 없음")
            if due and due[:10]<today and not t.get("done"):dl.setStyleSheet("color:#df6666;font-weight:bold")
            l.addWidget(dl)
            if t.get("subtasks"):l.addWidget(QLabel(f'☷ {sum(s.get("done",False) for s in t["subtasks"])}/{len(t["subtasks"])}'))
            e=QPushButton("편집"); e.clicked.connect(lambda _,tid=t["id"]:self.edit_id(tid)); l.addWidget(e)
            d=QPushButton("×"); d.setFixedWidth(32); d.clicked.connect(lambda _,tid=t["id"]:self.delete(tid)); l.addWidget(d)
            outer.addWidget(row)
            # 하위 체크리스트를 선택 없이 각 할 일 바로 아래에 항상 표시
            subs=t.get("subtasks",[])
            for sub in subs:
                sr=QWidget(); sl=QHBoxLayout(sr); sl.setContentsMargins(44,1,12,1); sl.setSpacing(8)
                scb=QPushButton("✓" if sub.get("done") else ""); scb.setCheckable(True); scb.setChecked(sub.get("done",False)); scb.setFixedSize(20,20)
                scb.setStyleSheet("QPushButton{border:2px solid #8c96a8;border-radius:10px;padding:0;font-weight:bold;background:#6f8fe0;color:white} QPushButton:!checked{background:transparent;color:transparent}")
                scb.clicked.connect(lambda checked,sid=sub["id"],tid=t["id"]:self.toggle_subtask(tid,sid,checked)); sl.addWidget(scb)
                st=QLabel(sub.get("title","")); st.setWordWrap(True)
                if sub.get("done"):st.setStyleSheet("text-decoration:line-through;color:#9299a8")
                sl.addWidget(st,1); outer.addWidget(sr)
            addrow=QWidget(); al=QHBoxLayout(addrow); al.setContentsMargins(44,1,12,4); self.subtask_inputs=getattr(self,"subtask_inputs",{})
            sin=QLineEdit(); sin.setPlaceholderText("+ 하위 체크리스트 추가..."); sin.setMaximumHeight(28); sin.returnPressed.connect(lambda tid=t["id"],w=sin:self.add_inline_subtask(tid,w)); al.addWidget(sin,1)
            sadd=QPushButton("+"); sadd.setFixedSize(28,28); sadd.clicked.connect(lambda _,tid=t["id"],w=sin:self.add_inline_subtask(tid,w)); al.addWidget(sadd); outer.addWidget(addrow)
            cardrow.setStyleSheet("QWidget{background:transparent}")
            self.list.addItem(it); self.list.setItemWidget(it,cardrow); it.setSizeHint(cardrow.sizeHint())
        if keep_id:
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole)==keep_id:
                    self.list.setCurrentItem(self.list.item(i)); break
        self.progress_today()
    def select_task(self,tid):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole)==tid:
                self.list.setCurrentItem(self.list.item(i)); return
    def edit_id(self,tid):
        t=next((x for x in self.tasks if x["id"]==tid),None)
        if t:self.edit_task(t)
    def delete(self,tid):
        t=next((x for x in self.tasks if x["id"]==tid),None)
        if t and QMessageBox.question(self,"삭제",f"{t['title']} 삭제할까요?")==QMessageBox.Yes:self.tasks.remove(t); self.save(); self.refresh()
    def toggle(self,tid,done):
        t=next((x for x in self.tasks if x["id"]==tid),None)
        if not t or t.get("done")==done:return
        t["done"]=done
        if done:
            t.setdefault("history",[]).append({"at":stamp(),"event":"완료"})
            self.repeat_next(t)
        else:
            t["repeat_next_date"]=""
            t.setdefault("history",[]).append({"at":stamp(),"event":"완료 취소"})
        self.save(); self.refresh()
    def next_repeat_date(self,base,r):
        typ=r.get("type","없음")
        if typ=="매일":return base+timedelta(days=1)
        if typ=="매주":
            days=r.get("weekdays",[])
            if not days:return base+timedelta(days=7)
            for off in range(1,15):
                cand=base+timedelta(days=off)
                if cand.weekday() in days:return cand
        if typ=="매월":
            y=base.year+base.month//12; m=base.month%12+1
            return date(y,m,min(int(r.get("monthday",base.day)),calendar.monthrange(y,m)[1]))
        return None
    def repeat_next(self,t):
        r=t.get("repeat",{}); typ=r.get("type","없음")
        if typ=="없음":t["repeat_next_date"]=""; return
        nxt=self.next_repeat_date(date.today(),r)
        t["repeat_next_date"]=nxt.isoformat() if nxt else ""
        if nxt:t.setdefault("history",[]).append({"at":stamp(),"event":"다음 반복 예약","next_due":nxt.isoformat()})
    def advance_repeats(self):
        today=date.today(); changed=False
        for t in self.tasks:
            if not t.get("done"):continue
            r=t.get("repeat",{}); typ=r.get("type","없음")
            nxts=t.get("repeat_next_date","")
            if typ=="없음" or not nxts:continue
            try:nxt=date.fromisoformat(nxts)
            except:continue
            # If the app was closed for several days, skip missed occurrences and wait for the next scheduled date.
            while nxt<today:
                if r.get("type")=="매일":
                    nxt=today
                    break
                following=self.next_repeat_date(nxt,r)
                if not following or following<=nxt:break
                nxt=following
            if nxt.isoformat()!=nxts:
                t["repeat_next_date"]=nxt.isoformat(); changed=True
            if nxt==today:
                t["done"]=False; t["repeat_next_date"]=""; t["start_date"]=nxt.isoformat()
                if r.get("time_none",False):t["due"]=nxt.isoformat()
                else:t["due"]=nxt.isoformat()+" "+r.get("time","09:00")
                t["reminded"]=[]; t.setdefault("history",[]).append({"at":stamp(),"event":"반복 작업 자동 복원","date":nxt.isoformat()}); changed=True
        return changed
    def reorder(self,*args):
        for i in range(self.list.count()):
            tid=self.list.item(i).data(Qt.UserRole)
            for t in self.tasks:
                if t["id"]==tid:t["order"]=i
        self.save()
    def progress_today(self):
        self.welcome.setText(date.today().strftime("%Y년 %m월 %d일")+" · 오늘의 할 일을 하나씩 체크해요")
    def show_subtasks(self,current,previous=None):
        while self.subitems.count():
            item=self.subitems.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.selected_task_id=current.data(Qt.UserRole) if current else None
        task=next((t for t in self.tasks if t.get("id")==self.selected_task_id),None)
        self.subhead.setText("Subtasks · "+task.get("title","") if task else "Subtasks · 할 일을 선택하세요")
        self.subinput.setEnabled(bool(task)); self.subadd.setEnabled(bool(task))
        if not task:return
        for sub in task.get("subtasks",[]):
            row=QWidget(); lay=QHBoxLayout(row); lay.setContentsMargins(2,2,2,2)
            cb=QPushButton("✓" if sub.get("done") else ""); cb.setCheckable(True); cb.setChecked(sub.get("done",False)); cb.setFixedSize(24,24)
            cb.setStyleSheet("QPushButton{border:2px solid #7e899c;border-radius:12px;padding:0;font-weight:bold;font-size:13pt;background:#6f8fe0;color:white} QPushButton:!checked{background:transparent;color:transparent}")
            cb.clicked.connect(lambda checked,sid=sub["id"],tid=task["id"]:self.toggle_subtask(tid,sid,checked)); lay.addWidget(cb)
            label=QLabel(sub.get("title","")); label.setWordWrap(True)
            if sub.get("done"):label.setStyleSheet("text-decoration:line-through;color:#9299a8")
            lay.addWidget(label,1); self.subitems.addWidget(row)
    def add_inline_subtask(self,tid,widget):
        title=widget.text().strip()
        task=next((t for t in self.tasks if t.get("id")==tid),None)
        if not task or not title:return
        task.setdefault("subtasks",[]).append({"id":str(uuid.uuid4()),"title":title,"done":False})
        self.save(); self.refresh_tasks()
        # 입력 후 해당 할 일은 그대로 선택
        self.select_task(tid)
    def add_subtask(self):
        title=self.subinput.text().strip(); tid=getattr(self,"selected_task_id",None)
        task=next((t for t in self.tasks if t.get("id")==tid),None)
        if not task or not title:return
        task.setdefault("subtasks",[]).append({"id":str(uuid.uuid4()),"title":title,"done":False}); self.subinput.clear(); self.save(); self.refresh_tasks(); self.select_task(tid)
    def toggle_subtask(self,tid,sid,done):
        task=next((t for t in self.tasks if t.get("id")==tid),None)
        if not task:return
        for sub in task.get("subtasks",[]):
            if sub.get("id")==sid:sub["done"]=done
        self.save(); self.refresh_tasks();
        self.select_task(tid)
    def set_calendar_mode(self, mode):
        if hasattr(self,"calendar_views"):
            weekly = mode == "WEEKLY"
            self.calendar_views.setCurrentIndex(0 if not weekly else 1)
            if hasattr(self,"calendar_right_panel"):
                self.calendar_right_panel.setVisible(not weekly)
            self.refresh_calendar()
    def set_calendar_default(self, mode):
        self.calendar_view_default=mode
        if hasattr(self,"calendar_mode") and self.calendar_mode.currentText()!=mode:
            # Save preference without changing the currently selected view.
            self.save()
        else:self.save()
    def shift_week(self, days):
        self.calendar.setSelectedDate(self.calendar.selectedDate().addDays(days))
        self.refresh_calendar()
    def refresh_weekly(self):
        if not hasattr(self,"weekgrid"): return
        while self.weekgrid.count():
            item=self.weekgrid.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        selected=self.calendar.selectedDate().toPython(); monday=selected-timedelta(days=selected.weekday()); sunday=monday+timedelta(days=6)
        self.weeklabel.setText(f"{monday:%Y-%m-%d}  —  {sunday:%Y-%m-%d}")
        names=["월","화","수","목","금","토","일"]
        # Date headers are clickable: selecting a date immediately opens the new-task dialog.
        for i in range(7):
            day=monday+timedelta(days=i); qd=QDate(day.year,day.month,day.day)
            color="#d93645" if i==6 else ("#2878d0" if i==5 else "#343a40")
            head=QPushButton(f"{names[i]}  {day.month}/{day.day}  +")
            head.setMinimumHeight(42); head.setStyleSheet(f"font-weight:bold;color:{color};padding:7px;background:#f8f9fc;border:1px solid #d9dce5;border-radius:7px")
            head.setToolTip("클릭하면 이 날짜에 할 일을 추가합니다")
            head.clicked.connect(lambda checked=False, q=qd:self.add_for_weekday(q))
            self.weekgrid.addWidget(head,0,i)
        # Build continuous task strips spanning their date range. Assign overlapping
        # intervals to separate lanes so that strips never cover each other.
        week_tasks=[]
        for t in self.tasks:
            if not t.get("show_in_calendar",False): continue
            try:
                st=date.fromisoformat((t.get("start_date") or t.get("due"))[:10])
                en=date.fromisoformat((t.get("due") or t.get("start_date"))[:10])
                if en<st: en=st
                if en<monday or st>sunday: continue
                left=max(0,(st-monday).days); right=min(6,(en-monday).days)
                week_tasks.append((left,right,t,st,en))
            except Exception: continue
        week_tasks.sort(key=lambda x:(x[0],-((x[1]-x[0])),x[2].get("done",False),x[2].get("title","")))
        lane_ends=[]; lane_rows=[]
        for left,right,t,st,en in week_tasks:
            lane=0
            while lane<len(lane_ends) and lane_ends[lane]>=left: lane+=1
            if lane==len(lane_ends): lane_ends.append(right)
            else: lane_ends[lane]=right
            lane_rows.append((lane,left,right,t,st,en))
        for lane,left,right,t,st,en in lane_rows:
            cat=next((c for c in self.cats if c.get("name")==t.get("category")),{"color":"#8aa4d6","emoji":"📌"})
            color=QColor(cat.get("color","#8aa4d6")); color.setAlpha(220)
            label=("✓  " if t.get("done") else "○  ")+cat.get("emoji","📌")+"  "+t.get("title","(제목 없음)")
            if st<monday or en>sunday:
                label=("← " if st<monday else "")+label+(" →" if en>sunday else "")
            tip=f"{t.get('title','')}\n{st:%Y-%m-%d} ~ {en:%Y-%m-%d}\n카테고리: {t.get('category','')}\n클릭하면 상세 포스트잇을 엽니다"
            bar=TaskStrip(label,cat.get("color","#8aa4d6"),tip)
            bar.clicked.connect(lambda task_id=t.get("id"):self.show_task_postit(task_id))
            self.weekgrid.addWidget(bar,lane+1,left,1,right-left+1)
        if not lane_rows:
            hint=QLabel("이번 주에 달력에 표시할 할 일이 없습니다. 날짜를 클릭해 추가하세요."); hint.setAlignment(Qt.AlignmentFlag.AlignCenter); hint.setStyleSheet("color:#7a8190;padding:22px")
            self.weekgrid.addWidget(hint,1,0,1,7)
        for i in range(7): self.weekgrid.setColumnStretch(i,1)
        self.weekgrid.setRowStretch(max(1,len(lane_ends)+1),1)

    def add_for_weekday(self, qdate):
        self.calendar.setSelectedDate(qdate)
        self.add_for_date(qdate)

    def show_task_postit(self, task_id):
        t=next((x for x in self.tasks if x.get("id")==task_id),None)
        if not t: return
        cat=next((c for c in self.cats if c.get("name")==t.get("category")),{"color":"#f6e7a8","emoji":"📌"})
        dlg=QDialog(self); dlg.setWindowTitle("할 일 포스트잇"); dlg.setMinimumWidth(360); dlg.setMaximumWidth(520)
        lay=QVBoxLayout(dlg); note=QFrame(); note.setObjectName("postit"); note.setStyleSheet(f"QFrame#postit{{background:{cat.get('color','#f6e7a8')};border:1px solid rgba(70,70,70,0.25);border-radius:10px}} QLabel{{background:transparent;color:#202435}}")
        nl=QVBoxLayout(note); nl.setContentsMargins(18,16,18,16); nl.setSpacing(9)
        title=QLabel(("✓ " if t.get("done") else "○ ")+cat.get("emoji","📌")+"  "+t.get("title","(제목 없음)")); title.setWordWrap(True); title.setStyleSheet("font-size:16pt;font-weight:bold"); nl.addWidget(title)
        dates=f"시작: {t.get('start_date','미지정')}\n마감: {t.get('due','미지정')}"
        details=QLabel(f"카테고리: {t.get('category','')}\n우선순위: {t.get('priority','보통')}\n{dates}"); details.setWordWrap(True); nl.addWidget(details)
        subs=t.get("subtasks",[]) or []
        if subs:
            nl.addWidget(QLabel("하위 체크리스트"))
            for sub in subs:
                sl=QLabel(("✓ " if sub.get("done") else "○ ")+sub.get("title","")); sl.setWordWrap(True); nl.addWidget(sl)
        repeat=t.get("repeat",{}); rt=repeat.get("type","없음")
        if rt!="없음": nl.addWidget(QLabel("반복: "+rt+(" · "+repeat.get("time","09:00") if not repeat.get("time_none") else " · 시간 없음")))
        lay.addWidget(note)
        buttons=QHBoxLayout(); edit=QPushButton("수정"); close=QPushButton("닫기"); buttons.addWidget(edit); buttons.addWidget(close); lay.addLayout(buttons)
        edit.clicked.connect(lambda: (dlg.accept(),self.edit_task(t,False)))
        close.clicked.connect(dlg.accept)
        dlg.exec()

    def refresh_calendar(self):
        if not hasattr(self,"calitems"):return
        d=self.calendar.selectedDate().toString("yyyy-MM-dd"); self.calhead.setText(d+"의 할 일"); self.calitems.clear()
        for t in sorted(self.tasks,key=lambda x:x.get("due","9999")):
            if not t.get("show_in_calendar",False):continue
            sd=t.get("start_date","")[:10]; due=t.get("due","")[:10]
            try:
                start=date.fromisoformat(sd) if sd else (date.fromisoformat(due) if due else None)
                end=date.fromisoformat(due) if due else start
                if start and end and start<=date.fromisoformat(d)<=end: matches=True
                else:matches=(sd==d or due==d)
            except:matches=(sd==d or due==d)
            if matches:
                c=next((c for c in self.cats if c["name"]==t.get("category")),{"color":"#8aa4d6","emoji":"📌"})
                item=QListWidgetItem(("✓ " if t.get("done") else "○ ")+c.get("emoji","📌")+" "+t.get("title","")+" · "+str(t.get("category","")))
                item.setBackground(QColor(c.get("color","#8aa4d6"))); item.setForeground(QColor("#202435")); item.setToolTip("카테고리: "+str(t.get("category",""))+"\n시작일: "+str(sd or "오늘")+"\n마감일: "+str(due or "오늘"))
                self.calitems.addItem(item)
        if not self.calitems.count():self.calitems.addItem("등록된 할 일이 없습니다.")
        self.refresh_weekly()
        self.mark_calendar_dates()
    def mark_calendar_dates(self):
        if not hasattr(self,"calendar"):return
        dates={}; years={self.calendar.yearShown(),self.calendar.yearShown()-1,self.calendar.yearShown()+1}
        for t in self.tasks:
            if not t.get("show_in_calendar",False):continue
            sd=t.get("start_date","")[:10]; due=t.get("due","")[:10]
            c=next((c for c in self.cats if c["name"]==t.get("category")),{"color":"#8aa4d6"})
            try:
                start=date.fromisoformat(sd) if sd else (date.fromisoformat(due) if due else None)
                end=date.fromisoformat(due) if due else start
                if start and end:
                    if end<start:end=start
                    cur=start
                    # Range bars are drawn day-by-day across the whole start-to-due span.
                    while cur<=end:
                        dates.setdefault(cur.isoformat(),[]).append({"color":c.get("color","#8aa4d6"),"title":t.get("title",""),"start":start.isoformat(),"due":end.isoformat()})
                        cur+=timedelta(days=1)
                        if len(dates)>20000:break
            except:pass
        self.calendar.set_day_entries(dates)
        holiday_dates=set()
        try:
            import holidays
            for y in years:
                holiday_dates.update(d.isoformat() for d in holidays.country_holidays("KR",years=[y]).keys())
        except Exception:
            # Fixed-date fallback if the Korean holiday package is unavailable.
            for y in years:
                for m,day in [(1,1),(3,1),(5,5),(6,6),(8,15),(10,3),(10,9),(12,25)]:holiday_dates.add(date(y,m,day).isoformat())
        self.calendar.set_holidays(holiday_dates)
        # Clear only formats previously used by this method, then color dates without filling their cells.
        for olddate in getattr(self,"_marked_dates",set()):
            qold=QDate.fromString(olddate,"yyyy-MM-dd")
            if qold.isValid():self.calendar.setDateTextFormat(qold,QTextCharFormat())
        self._marked_dates=set()
        all_dates=set(dates)|holiday_dates
        for key in all_dates:
            qd=QDate.fromString(key,"yyyy-MM-dd")
            if not qd.isValid():continue
            fmt=QTextCharFormat()
            if key in holiday_dates:fmt.setForeground(QColor("#d93645"))
            elif qd.dayOfWeek()==6:fmt.setForeground(QColor("#2878d0"))
            elif qd.dayOfWeek()==7:fmt.setForeground(QColor("#d93645"))
            if key in dates:fmt.setToolTip("\n".join([e["title"]+" · "+e["color"] for e in dates[key]]))
            self.calendar.setDateTextFormat(qd,fmt); self._marked_dates.add(key)
    def refresh(self):
        self.refresh_cats(); self.refresh_tasks(); self.refresh_calendar(); self.mark_calendar_dates()
    def refresh_cats(self):
        while self.catsbox.count():
            x=self.catsbox.takeAt(0)
            if x.widget():x.widget().deleteLater()
        b=QPushButton("⌕ 전체 보기"); b.clicked.connect(lambda:self.setcat("전체")); self.catsbox.addWidget(b)
        for c in self.cats:
            row=QWidget(); lay=QHBoxLayout(row); lay.setContentsMargins(0,0,0,0); lay.setSpacing(3)
            b=QPushButton(c["emoji"]+"  "+c["name"]); b.setToolTip(c["name"]); b.setMinimumWidth(90)
            active=(self.catfilter==c["name"]); color=c.get("color","#8aa4d6")
            b.setStyleSheet(f"text-align:left;font-weight:{'bold' if active else 'normal'};background:{color};color:#202435;border:1px solid {color}")
            b.clicked.connect(lambda _,n=c["name"]:self.setcat(n)); lay.addWidget(b,1)
            e=QPushButton("✎"); e.setFixedWidth(30); e.setToolTip("카테고리 수정"); e.clicked.connect(lambda _,n=c["name"]:self.editcat(n)); lay.addWidget(e)
            d=QPushButton("×"); d.setFixedWidth(30); d.setToolTip("카테고리 삭제"); d.clicked.connect(lambda _,n=c["name"]:self.deletecat(n)); lay.addWidget(d)
            self.catsbox.addWidget(row)
    def show_and_activate(self):
        self.showNormal(); self.raise_(); self.activateWindow()
    def notify(self,title,message):
        # Clickable Windows notification-area popup; clicking it focuses this app.
        try:
            if not hasattr(self,"tray"):
                self.tray=QSystemTrayIcon(self)
                self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
                self.tray.setToolTip(APP); self.tray.messageClicked.connect(self.show_and_activate); self.tray.show()
            self.tray.showMessage(title,message,QSystemTrayIcon.MessageIcon.Information,10000)
        except Exception:
            QMessageBox.information(self,title,message)
    def check_alerts(self,startup=False):
        changed=self.advance_repeats()
        now=datetime.now(); today=now.date().isoformat(); minute=now.strftime("%Y-%m-%d %H:%M")
        for t in self.tasks:
            if t.get("done"):continue
            due=t.get("due",""); r=t.get("reminder",""); keys=t.setdefault("reminded",[])
            if not r:continue
            if startup and r=="startup" and due[:10]==today and "startup:"+today not in keys:
                keys.append("startup:"+today); self.notify("BEST CHECKLIST","오늘 마감할 일: "+t["title"]); changed=True
            before_map={"due_before_5":5,"due_before_10":10,"due_before_30":30,"due_before_60":60}
            if r in before_map:
                try:
                    due_dt=datetime.strptime(due[:16],"%Y-%m-%d %H:%M") if len(due)>10 else datetime.strptime(due[:10]+" 09:00","%Y-%m-%d %H:%M")
                    first=due_dt-timedelta(minutes=before_map[r])
                    elapsed_minutes=int((now-first).total_seconds()//60)
                    unit=t.get("reminder_interval_unit","분")
                    interval=max(1,int(t.get("reminder_interval",5) or 5))*(60 if unit=="시간" else 1)
                    count=max(1,int(t.get("reminder_count",3) or 3))
                    index=elapsed_minutes//interval if elapsed_minutes>=0 else -1
                    key="before:"+r+":"+due_dt.strftime("%Y-%m-%d %H:%M")+":"+str(index)
                    if elapsed_minutes>=0 and index<count and key not in keys:
                        keys.append(key)
                        self.notify("마감 예정 알림",f'{t["title"]} · 마감 {before_map[r]}분 전 (알림 {index+1}/{count})')
                        changed=True
                except:pass
            if r=="custom" and t.get("reminder_at","") and t["reminder_at"]<=minute:
                try:
                    first=datetime.strptime(t["reminder_at"],"%Y-%m-%d %H:%M")
                    elapsed_minutes=int((now-first).total_seconds()//60); unit=t.get("reminder_interval_unit","분"); interval=max(1,int(t.get("reminder_interval",5) or 5))*(60 if unit=="시간" else 1)
                    index=elapsed_minutes//interval; count=max(1,int(t.get("reminder_count",3) or 3)); key="custom:"+str(first)+":"+str(index)
                    if elapsed_minutes>=0 and index<count and key not in keys:keys.append(key); self.notify("예약 알림",t["title"]); changed=True
                except:pass
            if r=="due" and len(due)>10 and due[:16]<=minute:
                try:
                    first=datetime.strptime(due[:16],"%Y-%m-%d %H:%M"); elapsed_minutes=int((now-first).total_seconds()//60); unit=t.get("reminder_interval_unit","분"); interval=max(1,int(t.get("reminder_interval",5) or 5))*(60 if unit=="시간" else 1)
                    index=max(0,elapsed_minutes)//interval; count=max(1,int(t.get("reminder_count",3) or 3)); key="due:"+due[:16]+":"+str(index)
                    if elapsed_minutes>=0 and index<count and key not in keys:keys.append(key); self.notify("마감 알림",t["title"]); changed=True
                except:pass
        if changed:self.save(); self.refresh()
        else:self.save()

    def backup(self):
        path,_=QFileDialog.getSaveFileName(self,"백업 내보내기","BEST_CHECKLIST_백업.json","JSON (*.json)")
        if path:
            try:
                with open(path,"w",encoding="utf-8") as f:
                    json.dump({"tasks":self.tasks,"categories":self.cats,"calendar_view_default":getattr(self,"calendar_view_default","Monthly")},f,ensure_ascii=False,indent=2)
                QMessageBox.information(self,"백업 내보내기","백업 파일을 저장했어요.")
            except Exception as e:QMessageBox.warning(self,"백업 오류",str(e))

    def import_backup(self):
        path,_=QFileDialog.getOpenFileName(self,"백업 가져오기","","JSON (*.json)")
        if not path:return
        try:
            with open(path,"r",encoding="utf-8-sig") as f:data=json.load(f)
            if not isinstance(data,dict) or not isinstance(data.get("tasks"),list):
                raise ValueError("올바른 BEST CHECKLIST 백업 파일이 아니에요. tasks 목록을 찾을 수 없습니다.")
            imported_cats=data.get("categories",CATS)
            if not isinstance(imported_cats,list):raise ValueError("카테고리 데이터 형식이 올바르지 않습니다.")
            clean_cats=[]
            for c in imported_cats:
                if isinstance(c,str):c={"name":c,"emoji":"📌","color":"#8aa4d6"}
                if isinstance(c,dict) and str(c.get("name","")).strip():
                    clean_cats.append({"name":str(c.get("name")).strip(),"emoji":str(c.get("emoji","📌")),"color":str(c.get("color","#8aa4d6"))})
            if not clean_cats:clean_cats=CATS.copy()
            valid_names={c["name"] for c in clean_cats}; clean_tasks=[]
            for old in data["tasks"]:
                if not isinstance(old,dict):continue
                t=newtask(); t.update(old)
                if not isinstance(t.get("repeat"),dict):t["repeat"]=newtask()["repeat"]
                for k,v in [("subtasks",[]),("history",[]),("reminded",[]),("reminder",""),("reminder_at",""),("reminder_interval",5),("reminder_interval_unit","분"),("reminder_count",3)]:t.setdefault(k,v)
                if not t.get("start_date"):t["start_date"]=date.today().isoformat()
                if not t.get("due"):t["due"]=date.today().isoformat()
                t.setdefault("date_enabled",False); t.setdefault("show_in_calendar",False)
                if t.get("category") not in valid_names:t["category"]=clean_cats[0]["name"]
                clean_tasks.append(t)
            answer=QMessageBox.question(self,"백업 가져오기","현재 Checklist 데이터를 가져온 백업 내용으로 교체할까요?\n\n현재 데이터는 앱에서 교체되므로, 필요하면 먼저 백업 내보내기를 해주세요.",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer!=QMessageBox.Yes:return
            self.tasks=clean_tasks; self.cats=clean_cats; self.catfilter="전체"
            self.save(); self.theme(); self.refresh_cats(); self.refresh(); self.check_alerts()
            QMessageBox.information(self,"백업 가져오기",f"백업을 가져왔어요.\n할 일 {len(self.tasks)}개, 카테고리 {len(self.cats)}개")
        except Exception as e:QMessageBox.warning(self,"백업 가져오기 오류",f"백업 파일을 읽지 못했어요.\n{e}")

def main():
    app=QApplication(sys.argv); app.setApplicationName(APP); w=App(); w.show(); sys.exit(app.exec())
if __name__=="__main__":main()
