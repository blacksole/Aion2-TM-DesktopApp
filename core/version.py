APP_NAME = "Aion2 Taskmanager"
APP_VERSION = "1.3.0"

GITHUB_USER = "blacksole"
GITHUB_REPO = "Aion2-TM-DesktopApp"

# Gates the Armory sidebar entry (Item Database / Crafting Calculator /
# Build Planner). Once this is True, Armory is a normal, permanent feature
# for everyone -- flip it here (one line) when it's ready to leave beta.
# Until then, users can still reach it early via the self-service "Beta
# Bereich freischalten" toggle in Settings (see MainWindow.
# _update_armory_visibility / armory_beta_enabled) -- opt-in, at their own
# risk, no separate branch/build needed for this.
ARMORY_ENABLED = False

# Shown in the Settings page's beta-unlock description ("...zeigt einen
# weiteren Bereich: {area}") -- kept as a plain constant here, not baked
# into the translated strings, since which area is "the current beta
# thing" changes as development moves on.
CURRENT_BETA_FEATURE_NAME = "Armory"