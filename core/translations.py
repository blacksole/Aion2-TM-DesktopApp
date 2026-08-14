DEFAULT_LANGUAGE = "en"

TRANSLATIONS = {
    "de": {

        # ================= APP =================
        "app_title": "Task & Shopping Manager",

        # ================= PROFILE =================
        "current_profile": 'Aktuelles Profil: "{name}"',
        "save_profile": "Profil sichern",
        "load_profile": "Profil laden ▾",
        "reset_profile": "Profil zurücksetzen",
        "profile_saved": "Profil gespeichert",
        "profile": "Profil",
        "profile_subtitle": "Profile verwalten und speichern",

        "reset_profile_tooltip":
        "Entfernt alle aktuellen Tasks- und Shopping-Einträge "
        "aus diesem Profil.\n\n"
        "Profileinstellungen und Layout bleiben erhalten.",

        # ================= GENERAL =================
        "add": "+ Hinzufügen",
        "save": "Speichern",
        "cancel": "Abbrechen",
        "title": "Titel",
        "description": "Beschreibung oder Ort",
        "progress": "Fortschritt",

        # ================= DISCORD =================
        "discord_connected": "Discord verbunden",
        "discord_not_connected": "Discord nicht verbunden",
        "online": "Online",
        "offline": "Offline",

        # ================= TASKS =================
        "daily_tasks": "📋 Tägl. Aufgaben",
        "weekly_tasks": "📅 Wöch. Aufgaben",
        "event_tasks": "🎉 Event Aufgaben",
        "tasks": "Aufgaben",
        "tasks_subtitle": "Daily, Weekly und Event Aufgaben",

        # ================= SHOPPING =================
        "daily_shopping": "🛒 Tägl. Einkauf",
        "weekly_shopping": "🛍️ Wöch. Einkauf",
        "event_shopping": "🎁 Event Einkauf",
        "shopping": "🛒 Einkauf",
        "priority": "Priorität",
        "priority_low": "Niedrig",
        "priority_middle": "Mittel",
        "priority_high": "Hoch",
        "location": "Ort",
        "amount": "Anzahl",
        "price": "Preis",
        "schedule_daily": "Daily",
        "schedule_weekly": "Weekly",
        "schedule_season": "Season",

        "daily_total_price": "Täglicher Gesamtpreis",
        "weekly_total_price": "Wöchentlicher Gesamtpreis",
        "event_total_price": "Event Gesamtpreis",
        "total_price": "Gesamtpreis",

        # ================= CLEAR EVENTS =================

        "clear_events": "Event-Einträge löschen",
        "clear_events_tooltip":
            "Entfernt alle Event-Einträge aus Aufgaben "
            "und Shopping-Listen.\n\n"
            "Normale Daily- und Weekly-Einträge bleiben erhalten.",
        "event_entries_removed": "✓ Event-Einträge gelöscht",

        # ================= SORTING =================
        "sort_by": "Sortieren nach ▾",
        "sort_by_title": "Titel",
        "sort_by_location": "Ort",
        "sort_by_price": "Preis",
        "sort_by_priority": "Priorität",

        # ================= FILTERING =================
        "filter_by": "Filtern nach ▾",
        "filter_by_all": "Alle",
        "filter_by_events": "Event",

        # ================= STATS =================
        "total": "Gesamt",
        "done": "Abgeschlossen",
        "remaining": "Verbleibend",

        # ================= TIMERS =================
        "daily_reset": "Tägl. Reset",
        "weekly_reset": "Wöch. Reset",
        "more_timers": "Weitere Timer",
        "show_shugo": "Shugo Event Timer anzeigen",
        "show_riss": "Riss Timer anzeigen",
        "timers": "Timer",
        "timers_subtitle": "Reset Timer und Erweiterte Timer",
        "shugo": "Shugo",
        "riss": "Riss",

        # ================= SETTINGS =================
        "settings": "Einstellungen",
        "general": "Allgemein",
        "layout": "Layout",
        "language": "Sprache",
        "display": "Anzeige",
        "system_time": "Systemzeit",
        "settings_saved": "Einstellungen gespeichert",
        "settings_title": "Einstellungen",
        "settings_subtitle": "App-, Layout- und Timer-Einstellungen",

        # ================= SETTINGS GENERAL =================
        "auto_save": "Automatisch speichern",
        "auto_save_desc": "Profiländerungen automatisch speichern.",
        "show_events_desc": "Event Aufgaben und Event Einkauf anzeigen.",
        "dps_meter":        "DPS Meter",
        "dps_meter_desc":   "Externe Anwendung beim Programmstart mitöffnen.",
        "dps_meter_browse": "Durchsuchen",
        "dps_meter_start":  "Mit TM starten",
        "about":            "Über Aion2 TM",
        "about_desc":       "Task Manager für Aion2 — Tägliche & wöchentliche Aufgaben, Timer, Flow Map.",
        "about_github":     "GitHub",
        "about_copy_ver":   "Version kopieren",

        # ================= RESET SETTINGS =================
        "reset_timer": "Reset Timer",
        "weekly_reset_day": "Wöch. Reset Wochentag",
        "weekly_reset_time": "Wöch. Reset Uhrzeit",
        "season_reset_label": "Season-Ende",

        # ================= ADVANCED TIMER =================
        "advanced_timer": "Erweiterte Timer",
        "notifications": "Benachrichtigungen",
        "shugo_timer": "Shugo Timer",
        "shugo_timer_desc": "Countdown für Shugo Events aktivieren.",
        "shugo_start": "Shugo Event Start (Min)",
        "shugo_interval": "Shugo Event Takt",
        "riss_timer": "Riss Timer",
        "riss_timer_desc": "Countdown für wiederkehrende Riss Events aktivieren.",
        "riss_anchor": "Riss Orientierungsstart (Uhrzeit)",
        "riss_interval": "Riss Takt",
        "start": "Start",
        "interval": "Intervall",
        "anchor": "Anker",
        "on": "Ein",
        "off": "Aus",
        "custom_timer":        "Custom Timer",
        "custom_timer_edit":   "Bearbeiten",
        "reset_timer_help":    "Zeigt die verbleibende Zeit bis zum täglichen und wöchentlichen Server-Reset an.",
        "advanced_timer_help": "Konfigurierbare Timer für Shugo- und Riss-Spawn-Zeiten mit individuellem Intervall.",
        "custom_timer_help":   "Erstelle eigene Timer mit individuellem Intervall, Farbe und Anzeigeformat (max. 8).",
        "shugo_help":          "Start gibt an, ab welcher Minute innerhalb einer Stunde der Timer beginnt.\nZ.B.: 0:15, 0:30, 0:45, 0:00",
        "riss_help":           "Anker ist der Startzeitpunkt des Timers.\nMitternacht, 01:00, 02:00 Uhr + Intervall",
        "reset_at":            "Reset in:",

        # ================= TIMER INTERVALS =================
        "timer_30min": "30 min",
        "timer_1h":    "1 Stunde",
        "timer_2h":    "2 Stunden",
        "timer_3h":    "3 Stunden",

        # ================= WEEKDAY ABBREVIATIONS =================
        "day_Mo": "Mo",
        "day_Di": "Di",
        "day_Mi": "Mi",
        "day_Do": "Do",
        "day_Fr": "Fr",
        "day_Sa": "Sa",
        "day_So": "So",

        # ================= MISC =================
        "no_sound":        "Kein Sound",
        "test_sound":      "▶ Test",
        "win_notif_title": "Windows Benachrichtigungen",
        "min_abbr":        "Min",
        "notif_sync":      "Synchron",
        "notif_nosync":    "Nicht-Synchron",
        "notif_shugo_warn": "Shugo Vorwarnung",
        "notif_riss_warn":  "Riss Vorwarnung",
        "notif_warn_label": "Vorwarnung",

        # ================= PLAN / FLOW MAP =================
        "plan": "Plan",

        "toast_plan_opened": "Ablaufplan geöffnet",

        "flow_title": "Ablaufplan",
        "flow_window_title": "Ablaufplan Map",

        "flow_edit_mode": "Plan bearbeiten",
        "flow_guide_mode": "Guide-Modus",

        "flow_add_node": "Knoten hinzufügen",
        "flow_edit_node": "Knoten bearbeiten",
        "flow_delete_node": "Knoten löschen",
        "flow_node_edit": "NODE BEARBEITEN",

        "flow_title_placeholder": "Titel",
        "flow_description_placeholder": "Beschreibung",
        "flow_symbol": "Symbol",
        "flow_optional_node": "Optionaler Knoten",

        "flow_new_node_title": "Neue Kachel",
        "flow_new_branch_title": "Neuer Branch",
        "flow_new_node_desc": "Beschreibung hinzufügen.",

        "flow_save": "Speichern",
        "flow_load": "Laden",

        "flow_status_colors": "STATUS & FARBEN",
        "status_completed": "Grün  =  Abgeschlossen",
        "status_active": "Blau  =  Aktiv",
        "status_optional": "Gelb  =  Optional / In Arbeit",
        "status_locked": "Grau  =  Zukünftig / Gesperrt",

        "flow_info_text": (
            "Kacheln können durch Klicken auf den Haken als erledigt markiert werden. "
            "Der nächste Schritt wird automatisch als aktiv markiert.  |  "
            "Strg + Klick: Mehrere Nodes auswählen"
        ),
        "flow_move_children": "Kinder mitbewegen",

        "flow_start_hint": "Klicke auf (+), um die erste Kachel zu erstellen.",

        "status_completed_short": "Abgeschlossen",
        "status_active_short": "Aktiv",
        "status_optional_short": "Optional",
        "status_locked_short": "Gesperrt",

        # ================= FLOW MAP UI =================
        "flow_saved": "✓ Gespeichert",
        "flow_saving": "Speichern...",
        "flow_zoom_hint": "Scrollen | Zoom {pct}%",
        "flow_mark_done":      "✓  Als erledigt markieren",
        "flow_mark_open":      "↩  Als offen markieren",
        "flow_tooltip_home": "Zur Wurzel",
        "flow_tooltip_select": "Auswählen",
        "flow_tooltip_add_node": "Knoten hinzufügen",
        "flow_tooltip_branch": "Branch",
        "flow_tooltip_delete": "Löschen",
        "flow_tooltip_new_map": "Neue Map erstellen",
        "flow_tooltip_delete_map": "Aktuelle Map löschen",
        "flow_tooltip_reset_map": "Map zurücksetzen",
        "flow_tool_prefix": "Werkzeug:",
        "event_badge": "EVENT",

        # ================= TIME VALUES =================
        "30_min": "30 Min",
        "1_hour": "1 Stunde",
        "2_hour": "2 Stunden",
        "3_hour": "3 Stunden",

        # ================= LANGUAGE =================
        "select_language": "Sprache auswählen",
        "application_language": "App-Sprache",
        "language_desc": "Wähle die Sprache der Anwendung.",

        # ================= PLACEHOLDERS =================
        "placeholder_daily_tasks": "Aufgabe",
        "placeholder_weekly_tasks": "Aufgabe",
        "placeholder_event_tasks": "Aufgabe",
        "placeholder_daily_shopping": "Itemname",
        "placeholder_shopping": "Itemname",
        "placeholder_weekly_shopping": "Itemname",
        "placeholder_event_shopping": "Itemname",
        "placeholder_tasks": "Quest",

        # ================= TOASTS =================
        "toast_tasks_opened": "Aufgaben geöffnet",
        "toast_timers_opened": "Timer geöffnet",
        "toast_settings_opened": "Einstellungen geöffnet",
        "toast_profile_opened": 'Profil: "{name}"',

        # ================= UPDATES =================
        "check_updates": "Nach Updates suchen",
        "check_updates_desc": "Manuell nach einer neuen App-Version suchen.",
        "check_updates_btn": "Jetzt prüfen",
        "update_available_toast": "Update v{version} verfügbar!",
        "up_to_date_toast": "App ist aktuell.",

        # ================= PROFILE TRANSFER =================
        "export_profile": "Profil exportieren",
        "import_profile": "Profil importieren",
        "duplicate_profile": "Profil duplizieren",
        "duplicate_profile_title": "Profil duplizieren",
        "duplicate_profile_label": "Name des neuen Profils:",
        "duplicate_profile_success": "Profil \"{name}\" wurde erstellt.",
        "profile_exported": "✓ Profil exportiert",
        "profile_imported": "✓ Profil importiert",
        "profile_import_error": "Ungültige Profil-Datei",

        # ================= DONATE =================
        "donate": "Unterstützen ❤",
        "donate_desc": "Die App gefällt dir? Eine kleine Spende hilft bei der Weiterentwicklung.",
        "donate_btn": "Spenden ☕",

        # ================= CONFIRM DIALOGS =================
        "confirm_reset_title": "Profil zurücksetzen?",
        "confirm_reset_text": "Möchtest du dein Profil wirklich zurücksetzen?\n\nAlle Tasks und Shopping-Einträge werden gelöscht.\nEinstellungen und Layout bleiben erhalten.",
        "confirm_clear_events_title": "Event-Einträge löschen?",
        "confirm_clear_events_text": "Möchtest du alle Event-Einträge wirklich löschen?\n\nDies betrifft alle Event-Tasks und Event-Shopping-Einträge.",
        "confirm_yes": "Ja, löschen",
        "confirm_no": "Abbrechen",

        # ================= TRAY =================
        "tray_minimize_title": "Beim Schließen im Tray minimieren?",
        "tray_minimize_text": "Soll das Programm beim Schließen im System-Tray verbleiben\noder wirklich beendet werden?",
        "tray_minimize_yes": "Im Tray minimieren",
        "tray_minimize_no": "Beenden",
        "tray_open": "Öffnen",
        "tray_exit": "Beenden",
        "tray_running": "Aion2 TM läuft im Hintergrund.",
        "tray_setting": "Im Tray minimieren",
        "tray_setting_desc": "Beim Schließen im System-Tray verbleiben statt zu beenden.",
    },

    "ru": {

        # ================= APP =================
        "app_title": "Менеджер задач и покупок",

        # ================= PROFILE =================
        "current_profile": 'Текущий профиль: "{name}"',
        "save_profile": "Сохранить профиль",
        "load_profile": "Загрузить профиль ▾",
        "reset_profile": "Сбросить профиль",
        "profile_saved": "Профиль сохранён",
        "profile": "Профиль",
        "profile_subtitle": "Управление и сохранение профилей",

        "reset_profile_tooltip":
        "Удаляет все текущие задачи и записи покупок "
        "из этого профиля.\n\n"
        "Настройки и макет профиля остаются без изменений.",

        # ================= GENERAL =================
        "add": "+ Добавить",
        "save": "Сохранить",
        "cancel": "Отмена",
        "title": "Название",
        "description": "Описание или место",
        "progress": "Прогресс",

        # ================= DISCORD =================
        "discord_connected": "Discord подключён",
        "discord_not_connected": "Discord не подключён",
        "online": "В сети",
        "offline": "Не в сети",

        # ================= TASKS =================
        "daily_tasks": "📋 Ежедневные задачи",
        "weekly_tasks": "📅 Еженедельные задачи",
        "event_tasks": "🎉 Событийные задачи",
        "tasks": "Задачи",
        "tasks_subtitle": "Ежедневные, еженедельные и событийные задачи",

        # ================= SHOPPING =================
        "daily_shopping": "🛒 Ежедневные покупки",
        "weekly_shopping": "🛍️ Еженедельные покупки",
        "event_shopping": "🎁 Событийные покупки",
        "shopping": "🛒 Покупки",
        "priority": "Приоритет",
        "priority_low": "Низкий",
        "priority_middle": "Средний",
        "priority_high": "Высокий",
        "location": "Место",
        "amount": "Количество",
        "price": "Цена",
        "schedule_daily": "Daily",
        "schedule_weekly": "Weekly",
        "schedule_season": "Season",

        "daily_total_price": "Ежедневная общая стоимость",
        "weekly_total_price": "Еженедельная общая стоимость",
        "event_total_price": "Стоимость события",
        "total_price": "Общая стоимость",

        # ================= CLEAR EVENTS =================
        "clear_events": "Удалить события",
        "clear_events_tooltip":
            "Удаляет все событийные записи из задач "
            "и списков покупок.\n\n"
            "Обычные ежедневные и еженедельные записи остаются.",
        "event_entries_removed": "✓ Событийные записи удалены",

        # ================= SORTING =================
        "sort_by": "Сортировка ▾",
        "sort_by_title": "Название",
        "sort_by_location": "Место",
        "sort_by_price": "Цена",
        "sort_by_priority": "Приоритет",

        # ================= FILTERING =================
        "filter_by": "Фильтр ▾",
        "filter_by_all": "Все",
        "filter_by_events": "Событие",

        # ================= STATS =================
        "total": "Всего",
        "done": "Выполнено",
        "remaining": "Осталось",

        # ================= TIMERS =================
        "daily_reset": "Ежедн. сброс",
        "weekly_reset": "Еженед. сброс",
        "more_timers": "Дополнительные таймеры",
        "show_shugo": "Показать таймер Shugo",
        "show_riss": "Показать таймер Riss",
        "timers": "Таймеры",
        "timers_subtitle": "Таймеры сброса и расширенные таймеры",
        "shugo": "Shugo",
        "riss": "Riss",

        # ================= SETTINGS =================
        "settings": "Настройки",
        "general": "Основные",
        "layout": "Интерфейс",
        "language": "Язык",
        "display": "Отображение",
        "system_time": "Системное время",
        "settings_saved": "Настройки сохранены",
        "settings_title": "Настройки",
        "settings_subtitle": "Настройки приложения, интерфейса и таймеров",

        # ================= SETTINGS GENERAL =================
        "auto_save": "Автосохранение",
        "auto_save_desc": "Автоматически сохранять изменения профиля.",
        "show_events_desc": "Показывать событийные задачи и покупки.",
        "dps_meter":        "DPS Meter",
        "dps_meter_desc":   "Открывать внешнее приложение при запуске программы.",
        "dps_meter_browse": "Обзор",
        "dps_meter_start":  "Запускать с TM",
        "about":            "Об Aion2 TM",
        "about_desc":       "Менеджер задач для Aion2 — Ежедневные и еженедельные задачи, таймеры, Flow Map.",
        "about_github":     "GitHub",
        "about_copy_ver":   "Скопировать версию",

        # ================= RESET SETTINGS =================
        "reset_timer": "Таймер сброса",
        "weekly_reset_day": "День еженедельного сброса",
        "weekly_reset_time": "Время еженедельного сброса",
        "season_reset_label": "Конец сезона",

        # ================= ADVANCED TIMER =================
        "advanced_timer": "Расширенные таймеры",
        "notifications": "Уведомления",
        "shugo_timer": "Таймер Shugo",
        "shugo_timer_desc": "Включить обратный отсчёт для событий Shugo.",
        "shugo_start": "Начало события Shugo (мин)",
        "shugo_interval": "Интервал Shugo",
        "riss_timer": "Таймер Riss",
        "riss_timer_desc": "Включить обратный отсчёт для повторяющихся событий Riss.",
        "riss_anchor": "Ориентировочное начало Riss (время)",
        "riss_interval": "Интервал Riss",
        "start": "Начало",
        "interval": "Интервал",
        "anchor": "Привязка",
        "on": "Вкл",
        "off": "Выкл",
        "custom_timer":        "Custom Timer",
        "custom_timer_edit":   "Изменить",
        "reset_timer_help":    "Показывает оставшееся время до ежедневного и еженедельного сброса сервера.",
        "advanced_timer_help": "Настраиваемые таймеры для событий Shugo и Riss с индивидуальным интервалом.",
        "custom_timer_help":   "Создавайте собственные таймеры с интервалом, цветом и форматом (макс. 8).",
        "shugo_help":          "Начало — с какой минуты внутри часа срабатывает таймер.\nНапр.: 0:15, 0:30, 0:45, 0:00",
        "riss_help":           "Привязка — начальная точка отсчёта таймера.\nПолночь, 01:00, 02:00 ночи + интервал",
        "reset_at":            "Сброс через:",

        # ================= TIMER INTERVALS =================
        "timer_30min": "30 мин",
        "timer_1h":    "1 час",
        "timer_2h":    "2 часа",
        "timer_3h":    "3 часа",

        # ================= WEEKDAY ABBREVIATIONS =================
        "day_Mo": "Пн",
        "day_Di": "Вт",
        "day_Mi": "Ср",
        "day_Do": "Чт",
        "day_Fr": "Пт",
        "day_Sa": "Сб",
        "day_So": "Вс",

        # ================= MISC =================
        "no_sound":        "Без звука",
        "test_sound":      "▶ Тест",
        "win_notif_title": "Уведомления Windows",
        "min_abbr":        "мин",
        "notif_sync":      "Синхронно",
        "notif_nosync":    "Не синхронно",
        "notif_shugo_warn": "Предупр. Shugo",
        "notif_riss_warn":  "Предупр. Riss",
        "notif_warn_label": "Предупреждение",

        # ================= PLAN / FLOW MAP =================
        "plan": "План",
        "toast_plan_opened": "План открыт",
        "flow_title": "Блок-схема",
        "flow_window_title": "Карта блок-схемы",

        "flow_add_node": "Добавить узел",
        "flow_edit_node": "Редактировать узел",
        "flow_delete_node": "Удалить узел",
        "flow_node_edit": "РЕДАКТИРОВАНИЕ УЗЛА",

        "flow_edit_mode": "Редактировать план",
        "flow_guide_mode": "Режим гида",

        "flow_title_placeholder": "Название",
        "flow_description_placeholder": "Описание",
        "flow_symbol": "Символ",
        "flow_optional_node": "Необязательный узел",

        "flow_new_node_title": "Новый узел",
        "flow_new_branch_title": "Новая ветка",
        "flow_new_node_desc": "Добавить описание.",

        "flow_save": "Сохранить",
        "flow_load": "Загрузить",

        "flow_status_colors": "СТАТУС И ЦВЕТА",
        "status_completed": "Зелёный  =  Выполнено",
        "status_active": "Синий    =  Активно",
        "status_optional": "Жёлтый  =  Опционально / В процессе",
        "status_locked": "Серый    =  Будущее / Заблокировано",

        "flow_info_text": (
            "Плитки можно отметить как выполненные, нажав на галочку. "
            "Следующий шаг автоматически станет активным.  |  "
            "Ctrl + клик: выбрать несколько узлов"
        ),
        "flow_move_children": "Перемещать дочерние узлы",

        "flow_start_hint": "Нажмите (+), чтобы создать первую плитку.",

        "status_completed_short": "Выполнено",
        "status_active_short": "Активно",
        "status_optional_short": "Опционально",
        "status_locked_short": "Заблокировано",

        # ================= FLOW MAP UI =================
        "flow_saved": "✓ Сохранено",
        "flow_saving": "Сохранение...",
        "flow_zoom_hint": "Прокрутка | Масштаб {pct}%",
        "flow_mark_done":      "✓  Отметить как выполненное",
        "flow_mark_open":      "↩  Отметить как открытое",
        "flow_tooltip_home": "К корню",
        "flow_tooltip_select": "Выбрать",
        "flow_tooltip_add_node": "Добавить узел",
        "flow_tooltip_branch": "Ветка",
        "flow_tooltip_delete": "Удалить",
        "flow_tooltip_new_map": "Новая карта",
        "flow_tooltip_delete_map": "Удалить текущую карту",
        "flow_tooltip_reset_map": "Сбросить карту",
        "flow_tool_prefix": "Инструмент:",
        "event_badge": "СОБЫТИЕ",

        # ================= TIME VALUES =================
        "30_min": "30 мин",
        "1_hour": "1 час",
        "2_hour": "2 часа",
        "3_hour": "3 часа",

        # ================= LANGUAGE =================
        "select_language": "Выбрать язык",
        "application_language": "Язык приложения",
        "language_desc": "Выберите язык интерфейса приложения.",

        # ================= PLACEHOLDERS =================
        "placeholder_daily_tasks": "Задача",
        "placeholder_weekly_tasks": "Задача",
        "placeholder_event_tasks": "Задача",
        "placeholder_daily_shopping": "Itemname",
        "placeholder_shopping": "Itemname",
        "placeholder_weekly_shopping": "Itemname",
        "placeholder_event_shopping": "Itemname",
        "placeholder_tasks": "Квест",

        # ================= TOASTS =================
        "toast_tasks_opened": "Задачи открыты",
        "toast_timers_opened": "Таймеры открыты",
        "toast_settings_opened": "Настройки открыты",
        "toast_profile_opened": 'Профиль: "{name}"',

        # ================= UPDATES =================
        "check_updates": "Проверить обновления",
        "check_updates_desc": "Вручную проверить наличие новой версии приложения.",
        "check_updates_btn": "Проверить",
        "update_available_toast": "Доступно обновление v{version}!",
        "up_to_date_toast": "Приложение актуально.",

        # ================= PROFILE TRANSFER =================
        "export_profile": "Экспорт профиля",
        "import_profile": "Импорт профиля",
        "duplicate_profile": "Дублировать профиль",
        "duplicate_profile_title": "Дублировать профиль",
        "duplicate_profile_label": "Имя нового профиля:",
        "duplicate_profile_success": "Профиль \"{name}\" создан.",
        "profile_exported": "✓ Профиль экспортирован",
        "profile_imported": "✓ Профиль импортирован",
        "profile_import_error": "Неверный файл профиля",

        # ================= DONATE =================
        "donate": "Поддержать ❤",
        "donate_desc": "Нравится приложение? Небольшое пожертвование помогает развитию.",
        "donate_btn": "Пожертвовать ☕",

        # ================= CONFIRM DIALOGS =================
        "confirm_reset_title": "Сбросить профиль?",
        "confirm_reset_text": "Вы действительно хотите сбросить профиль?\n\nВсе задачи и записи покупок будут удалены.\nНастройки и макет останутся без изменений.",
        "confirm_clear_events_title": "Удалить событийные записи?",
        "confirm_clear_events_text": "Вы действительно хотите удалить все событийные записи?\n\nЭто затронет все событийные задачи и покупки.",
        "confirm_yes": "Да, удалить",
        "confirm_no": "Отмена",

        # ================= TRAY =================
        "tray_minimize_title": "Свернуть в трей при закрытии?",
        "tray_minimize_text": "Свернуть программу в системный трей\nили завершить её?",
        "tray_minimize_yes": "Свернуть в трей",
        "tray_minimize_no": "Завершить",
        "tray_open": "Открыть",
        "tray_exit": "Выйти",
        "tray_running": "Aion2 TM работает в фоне.",
        "tray_setting": "Свернуть в трей",
        "tray_setting_desc": "При закрытии оставаться в системном трее.",
    },

    "en": {

        # ================= APP =================
        "app_title": "Task & Shopping Manager",

        # ================= PROFILE =================
        "current_profile": 'Current profile: "{name}"',
        "save_profile": "Save Profile",
        "load_profile": "Load Profile ▾",
        "reset_profile": "Reset Profile",
        "profile_saved": "Profile saved",
        "profile": "Profile",
        "profile_subtitle": "Manage and save profiles",

        "reset_profile_tooltip":
        "Removes all current Tasks and Shopping entries "
        "from this profile.\n\n"
        "Profile settings and layout will remain unchanged.",

        # ================= GENERAL =================
        "add": "+ Add",
        "save": "Save",
        "cancel": "Cancel",
        "title": "Title",
        "description": "Description or location",
        "progress": "Progress",

        # ================= DISCORD =================
        "discord_connected": "Discord connected",
        "discord_not_connected": "Discord not connected",
        "online": "Online",
        "offline": "Offline",

        # ================= TASKS =================
        "daily_tasks": "📋 Daily Tasks",
        "weekly_tasks": "📅 Weekly Tasks",
        "event_tasks": "🎉 Event Tasks",
        "tasks": "Tasks",
        "tasks_subtitle": "Daily, weekly and event tasks",

        # ================= SHOPPING =================
        "daily_shopping": "🛒 Daily Shopping",
        "weekly_shopping": "🛍️ Weekly Shopping",
        "event_shopping": "🎁 Event Shopping",
        "shopping": "🛒 Shopping",
        "priority": "Priority",
        "priority_low": "Low",
        "priority_middle": "Medium",
        "priority_high": "High",
        "location": "Location",
        "amount": "Amount",
        "price": "Price",
        "schedule_daily": "Daily",
        "schedule_weekly": "Weekly",
        "schedule_season": "Season",

        "daily_total_price": "Daily Total Price",
        "weekly_total_price": "Weekly Total Price",
        "event_total_price": "Event Total Price",
        "total_price": "Total Price",

        # ================= CLEAR EVENTS =================
        "clear_events": "Clear Event Entries",
        "clear_events_tooltip":
            "Removes all Event entries from Tasks "
            "and Shopping lists.\n\n"
            "Normal Daily and Weekly entries remain unchanged.",
        "event_entries_removed": "✓ Event entries removed",

        # ================= SORTING =================
        "sort_by": "Sort by ▾",
        "sort_by_title": "Title",
        "sort_by_location": "Location",
        "sort_by_price": "Price",
        "sort_by_priority": "Priority",

        # ================= FILTERING =================
        "filter_by": "Filter by ▾",
        "filter_by_all": "All",
        "filter_by_events": "Event",

        # ================= STATS =================
        "total": "Total",
        "done": "Completed",
        "remaining": "Remaining",

        # ================= TIMERS =================
        "daily_reset": "Daily Reset",
        "weekly_reset": "Weekly Reset",
        "more_timers": "Additional Timers",
        "show_shugo": "Show Shugo Event Timer",
        "show_riss": "Show Rift Timer",
        "timers": "Timers",
        "timers_subtitle": "Reset timers and advanced timers",
        "shugo": "Shugo",
        "riss": "Rift",

        # ================= SETTINGS =================
        "settings": "Settings",
        "general": "General",
        "layout": "Layout",
        "language": "Language",
        "display": "Display",
        "system_time": "System time",
        "settings_saved": "Settings saved",
        "settings_title": "Settings",
        "settings_subtitle": "App, layout and timer settings",

        # ================= SETTINGS GENERAL =================
        "auto_save": "Auto Save",
        "auto_save_desc": "Automatically save profile changes.",
        "show_events_desc": "Show event tasks and event shopping.",
        "dps_meter":        "DPS Meter",
        "dps_meter_desc":   "Open an external application when the program starts.",
        "dps_meter_browse": "Browse",
        "dps_meter_start":  "Start with TM",
        "about":            "About Aion2 TM",
        "about_desc":       "Task Manager for Aion2 — Daily & weekly tasks, timers, Flow Map.",
        "about_github":     "GitHub",
        "about_copy_ver":   "Copy version",

        # ================= RESET SETTINGS =================
        "reset_timer": "Reset Timer",
        "weekly_reset_day": "Weekly Reset Day",
        "weekly_reset_time": "Weekly Reset Time",
        "season_reset_label": "Season End",

        # ================= ADVANCED TIMER =================
        "advanced_timer": "Advanced Timer",
        "notifications": "Notifications",
        "shugo_timer": "Shugo Timer",
        "shugo_timer_desc": "Enable spawn countdown for Shugo events.",
        "shugo_start": "Shugo Event Start (Min)",
        "shugo_interval": "Shugo Event Interval",
        "riss_timer": "Rift Timer",
        "riss_timer_desc": "Enable countdown for recurring Rift events.",
        "riss_anchor": "Rift Orientation Start (Daytime)",
        "riss_interval": "Rift Interval",
        "start": "Start",
        "interval": "Interval",
        "anchor": "Anchor",
        "on": "On",
        "off": "Off",
        "custom_timer":        "Custom Timer",
        "custom_timer_edit":   "Edit",
        "reset_timer_help":    "Shows the remaining time until the daily and weekly server reset.",
        "advanced_timer_help": "Configurable timers for Shugo and Rift spawn times with custom intervals.",
        "custom_timer_help":   "Create custom timers with individual interval, color and display format (max. 8).",
        "shugo_help":          "Start means when does it start within 1 Hour.\nF.e.: 0:15, 0:30, 0:45, 0:00",
        "riss_help":           "Anchor means what time your Timer starts at.\nMidnight, 01:00, 02:00 at Night + Interval",
        "reset_at":            "Reset in:",

        # ================= TIMER INTERVALS =================
        "timer_30min": "30 min",
        "timer_1h":    "1 hour",
        "timer_2h":    "2 hours",
        "timer_3h":    "3 hours",

        # ================= WEEKDAY ABBREVIATIONS =================
        "day_Mo": "Mo",
        "day_Di": "Tu",
        "day_Mi": "We",
        "day_Do": "Th",
        "day_Fr": "Fr",
        "day_Sa": "Sa",
        "day_So": "Su",

        # ================= MISC =================
        "no_sound":        "No Sound",
        "test_sound":      "▶ Test",
        "win_notif_title": "Windows Notifications",
        "min_abbr":        "min",
        "notif_sync":      "Synchronized",
        "notif_nosync":    "Separate",
        "notif_shugo_warn": "Shugo Warn",
        "notif_riss_warn":  "Riss Warn",
        "notif_warn_label": "Warn before",

        # ================= TOAST PLANS =================
        "toast_plan_opened": "Plan opened",
        "plan": "Plan",

        "flow_title": "Flow",
        "flow_window_title": "Flow Map",

        "flow_add_node": "Add Node",
        "flow_edit_node": "Edit Node",
        "flow_delete_node": "Delete Node",
        "flow_node_edit": "EDIT NODE",

        "flow_edit_mode": "Edit plan",
        "flow_guide_mode": "Guide mode",

        "flow_title_placeholder": "Title",
        "flow_description_placeholder": "Description",
        "flow_symbol": "Symbol",
        "flow_optional_node": "Optional Node",

        "flow_new_node_title": "New Node",
        "flow_new_branch_title": "New Branch",
        "flow_new_node_desc": "Add a description.",

        "flow_save": "Save",
        "flow_load": "Load",

        "flow_status_colors": "STATUS & COLORS",
        "status_completed": "Green  =  Completed",
        "status_active": "Blue   =  Active",
        "status_optional": "Yellow =  Optional / In Progress",
        "status_locked": "Gray   =  Future / Locked",

        "flow_info_text": (
            "Tiles can be marked as completed by clicking the checkmark. "
            "The next step will automatically be marked as active.  |  "
            "Ctrl + Click: Select multiple nodes"
        ),
        "flow_move_children": "Move children with parent",

        "flow_start_hint": "Click (+) to create the first card.",

        "status_completed_short": "Completed",
        "status_active_short": "Active",
        "status_optional_short": "Optional",
        "status_locked_short": "Locked",


        # ================= FLOW MAP UI =================
        "flow_saved": "✓ Saved",
        "flow_saving": "Saving...",
        "flow_zoom_hint": "Scroll | Zoom {pct}%",
        "flow_mark_done":      "✓  Mark as completed",
        "flow_mark_open":      "↩  Mark as open",
        "flow_tooltip_home": "Go to Root",
        "flow_tooltip_select": "Select",
        "flow_tooltip_add_node": "Add Node",
        "flow_tooltip_branch": "Branch",
        "flow_tooltip_delete": "Delete",
        "flow_tooltip_new_map": "New Map",
        "flow_tooltip_delete_map": "Delete current map",
        "flow_tooltip_reset_map": "Reset map",
        "flow_tool_prefix": "Tool:",
        "event_badge": "EVENT",

        # ================= TIME VALUES =================
        "30_min": "30 Min",
        "1_hour": "1 Hour",
        "2_hour": "2 Hours",
        "3_hour": "3 Hours",

        # ================= LANGUAGE =================
        "select_language": "Select language",
        "application_language": "Application Language",
        "language_desc": "Choose the language used by the application.",

        # ================= PLACEHOLDERS =================
        "placeholder_daily_tasks": "Task",
        "placeholder_weekly_tasks": "Task",
        "placeholder_event_tasks": "Task",
        "placeholder_daily_shopping": "Itemname",
        "placeholder_shopping": "Itemname",
        "placeholder_weekly_shopping": "Itemname",
        "placeholder_event_shopping": "Itemname",
        "placeholder_tasks": "Quest",

        # ================= TOASTS =================
        "toast_tasks_opened": "Tasks opened",
        "toast_timers_opened": "Timers opened",
        "toast_settings_opened": "Settings opened",
        "toast_profile_opened": 'Profile: "{name}"',

        # ================= UPDATES =================
        "check_updates": "Check for Updates",
        "check_updates_desc": "Manually check for a new app version.",
        "check_updates_btn": "Check now",
        "update_available_toast": "Update v{version} available!",
        "up_to_date_toast": "App is up to date.",

        # ================= PROFILE TRANSFER =================
        "export_profile": "Export Profile",
        "import_profile": "Import Profile",
        "duplicate_profile": "Duplicate Profile",
        "duplicate_profile_title": "Duplicate Profile",
        "duplicate_profile_label": "Name of the new profile:",
        "duplicate_profile_success": "Profile \"{name}\" has been created.",
        "profile_exported": "✓ Profile exported",
        "profile_imported": "✓ Profile imported",
        "profile_import_error": "Invalid profile file",

        # ================= DONATE =================
        "donate": "Support ❤",
        "donate_desc": "Enjoying the app? A small donation helps keep it going.",
        "donate_btn": "Donate ☕",

        # ================= CONFIRM DIALOGS =================
        "confirm_reset_title": "Reset Profile?",
        "confirm_reset_text": "Do you really want to reset your profile?\n\nAll tasks and shopping entries will be deleted.\nSettings and layout will remain unchanged.",
        "confirm_clear_events_title": "Delete Event Entries?",
        "confirm_clear_events_text": "Do you really want to delete all event entries?\n\nThis affects all event tasks and event shopping entries.",
        "confirm_yes": "Yes, delete",
        "confirm_no": "Cancel",

        # ================= TRAY =================
        "tray_minimize_title": "Minimize to tray on close?",
        "tray_minimize_text": "Should the program minimize to the system tray\nor close completely?",
        "tray_minimize_yes": "Minimize to tray",
        "tray_minimize_no": "Close",
        "tray_open": "Open",
        "tray_exit": "Exit",
        "tray_running": "Aion2 TM is running in the background.",
        "tray_setting": "Minimize to tray",
        "tray_setting_desc": "Stay in the system tray instead of closing.",
    }
}


def tr(language, key, **kwargs):
    text = TRANSLATIONS.get(
        language,
        TRANSLATIONS[DEFAULT_LANGUAGE]
    ).get(key, key)

    return text.format(**kwargs)