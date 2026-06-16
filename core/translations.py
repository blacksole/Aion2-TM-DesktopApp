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
        "priority": "Priorität",
        "priority_low": "Niedrig",
        "priority_middle": "Mittel",
        "priority_high": "Hoch",
        "location": "Ort",
        "amount": "Anzahl",
        "price": "Preis",

        "daily_total_price": "Täglicher Gesamtpreis",
        "weekly_total_price": "Wöchentlicher Gesamtpreis",
        "event_total_price": "Event Gesamtpreis",

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

        # ================= RESET SETTINGS =================
        "reset_timer": "Reset Timer",
        "weekly_reset_day": "Wöch. Reset Wochentag",
        "weekly_reset_time": "Wöch. Reset Uhrzeit",

        # ================= ADVANCED TIMER =================
        "advanced_timer": "Erweiterte Timer",
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

        "flow_edit_mode": "Plan bearbeiten",
        "flow_guide_mode": "Guide-Modus",

        "flow_title_placeholder": "Titel",
        "flow_description_placeholder": "Beschreibung",
        "flow_symbol": "Symbol",
        "flow_optional_node": "Optionaler Knoten",

        "flow_new_node_title": "Neue Kachel",
        "flow_new_branch_title": "Neuer Branch",
        "flow_new_node_desc": "Beschreibung hinzufügen.",

        "flow_save": "Speichern",
        "flow_load": "Laden",

        "cancel": "Abbrechen",

        "flow_status_colors": "STATUS & FARBEN",
        "status_completed": "Grün  =  Abgeschlossen",
        "status_active": "Blau  =  Aktiv",
        "status_optional": "Gelb  =  Optional / In Arbeit",
        "status_locked": "Grau  =  Zukünftig / Gesperrt",

        "flow_info_text": (
            "Kacheln können durch Klicken auf den Haken als erledigt markiert werden.\n"
            "Der nächste Schritt wird automatisch als aktiv markiert."
        ),

        "flow_start_hint": "Klicke auf (+), um die erste Kachel zu erstellen.",

        "status_completed_short": "Abgeschlossen",
        "status_active_short": "Aktiv",
        "status_optional_short": "Optional",
        "status_locked_short": "Gesperrt",

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
        "placeholder_daily_tasks": "Titel der täglichen Aufgabe",
        "placeholder_weekly_tasks": "Titel der wöchentlichen Aufgabe",
        "placeholder_event_tasks": "Titel der Event-Aufgabe",
        "placeholder_daily_shopping": "Titel des täglichen Einkaufs",
        "placeholder_weekly_shopping": "Titel des wöchentlichen Einkaufs",
        "placeholder_event_shopping": "Titel des Event-Einkaufs",

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
        "priority": "Priority",
        "priority_low": "Low",
        "priority_middle": "Medium",
        "priority_high": "High",
        "location": "Location",
        "amount": "Amount",
        "price": "Price",

        "daily_total_price": "Daily Total Price",
        "weekly_total_price": "Weekly Total Price",
        "event_total_price": "Event Total Price",

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

        # ================= RESET SETTINGS =================
        "reset_timer": "Reset Timer",
        "weekly_reset_day": "Weekly Reset Day",
        "weekly_reset_time": "Weekly Reset Time",

        # ================= ADVANCED TIMER =================
        "advanced_timer": "Advanced Timer",
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

        "save": "Save",
        "cancel": "Cancel",

        "flow_status_colors": "STATUS & COLORS",
        "status_completed": "Green  =  Completed",
        "status_active": "Blue   =  Active",
        "status_optional": "Yellow =  Optional / In Progress",
        "status_locked": "Gray   =  Future / Locked",

        "flow_info_text": (
            "Tiles can be marked as completed by clicking the checkmark.\n"
            "The next step will automatically be marked as active."
        ),

        "flow_start_hint": "Click (+) to create the first card.",

        "status_completed_short": "Completed",
        "status_active_short": "Active",
        "status_optional_short": "Optional",
        "status_locked_short": "Locked",


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
        "placeholder_daily_tasks": "Title daily task",
        "placeholder_weekly_tasks": "Title weekly task",
        "placeholder_event_tasks": "Title event task",
        "placeholder_daily_shopping": "Title daily shopping",
        "placeholder_weekly_shopping": "Title weekly shopping",
        "placeholder_event_shopping": "Title event shopping",

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
    }
}


def tr(language, key, **kwargs):
    text = TRANSLATIONS.get(
        language,
        TRANSLATIONS[DEFAULT_LANGUAGE]
    ).get(key, key)

    return text.format(**kwargs)