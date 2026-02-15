# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A kanata (keyboard remapper for Linux) configuration with an **app-polymorphic action system** — the same key combo dispatches different actions depending on the active application (nvim, chrome, obsidian, tmux, etc.).

## Key Commands

```bash
# Sync all app action files with the shared interface (after editing actions.kbd):
./scripts/kanata_sync_all_apps_interfaces.sh

# Sync a single app file (dry-run, prints to stdout):
./scripts/kanata_sync_interfaces.py actions/actions_chrome.4.kbd
# Write mode:
./scripts/kanata_sync_interfaces.py -w actions/actions_chrome.4.kbd

# Regenerate kanata.kbd virtual keys + actions.kbd switch conditions (after adding/removing app files):
./scripts/kanata_sync_apps.py -f

# Reload kanata config: Tab+r

# Run kanata_sync_interfaces and kanata_sync_apps (Tab+shift+r)

# Restart kanata service:
systemctl --user restart kanata.service

# View logs:
journalctl --user -u kanata -f -n 100

# NOTE: kanata service runs by default listening at port 10101. Other software,
like KWanata can send kanata virtual keys or layers instructions to make
kanata app aware.
```

## Architecture

### File Relationships

```
kanata.kbd  (entry point, includes everything)
  ├── templates.kbd       (reusable macros: homerowmod, tap-dance, layer toggles, etc.)
  ├── setup.kbd           (defsrc, default layers, homerow mod aliases)
  ├── layers.kbd          (layer toggle variables + 30+ deflayermaps)
  └── actions/
      ├── actions.kbd     (shared action interface — all @autogen@ tagged switch statements)
      ├── actions_nvim.1.kbd      (priority 1, highest)
      ├── actions_chrome.4.kbd
      ├── actions_dolphin.4.kbd
      ├── actions_obsidian.4.kbd
      ├── actions_foot.9.kbd
      ├── actions_tmux.98.kbd
      └── actions_zellij.99.kbd   (priority 99, lowest)
```

### App-Polymorphism Pattern

Each app has a virtual key (`vk_<app>`) toggled by external software when the app gains/loses focus. Actions in `actions.kbd` use `(switch ;;@autogen@` to dispatch based on which virtual key is pressed:

```lisp
action_tab_next (t! unmod_all (switch ;;@autogen@
  ((input virtual vk_nvim)) $nvim_action_tab_next break
  ((input virtual vk_chrome)) $chrome_action_tab_next break
  () C-tab break   ;; default fallback
))
```

- **Priority**: Lower filename index = checked first. `actions_nvim.1.kbd` beats `actions_tmux.98.kbd`.
- **Reversed actions**: `~action_lsft+name>` checks apps in reverse order, enabling alternate behavior when apps overlap (e.g. nvim inside tmux).
- App files can define **app variables** (e.g. `tmux_prefix A-b`) and **app-specific actions** not in the shared interface — both are preserved by the sync scripts.

### Sync Workflow

1. **Adding a new action**: Edit `actions.kbd`, add the action with `;;@autogen@` tag, then run `kanata_sync_all_apps_interfaces.sh` to propagate the placeholder to all app files.
2. **Adding a new app**: Create `actions/actions_<app>.<priority>.kbd`, then run `kanata_sync_apps.py -f` to register it in `kanata.kbd` and `actions.kbd`.
3. **Implementing an app action**: Uncomment the placeholder line in the app file (e.g. change `;;  tmux_action_tab_new` to `tmux_action_tab_new (macro $tmux_prefix c)`), then run `kanata_sync_apps.py -f` to wire it into `actions.kbd` switch conditions.

### Layer System

- **Homerow mods**: `a/s/d/f/g/h/j/k/l/;` act as `gui/lalt/lsft/lctl/lmet/lmet/lctl/rsft/lalt/gui` when held, with fast-typing detection to prevent misfires.
- **Physical key remapping**: `lctl→lmet`, `lmet→lalt`, `lalt→lctl` (Mac-like `ctrl|alt|cmd` layout).
- **Modifier layers compose**: holding `lctl` activates `lctl_layer`; then holding `lalt` on top activates `lctl+lalt_layer`, etc. up to 3-modifier combos.
- **`!` prefix layers**: There are 2 sets of modifiers: homerow keys (lctl/lalt/lmet) and physical keyboard keys (!lctl/!lalt/!lmet). In normal apps they have the same functionality. In apps with a vim mode, you get 2 sets of functionality: one for vim-mode commands, the other for the app's own commands (e.g. obsidian, VS Code).
- **Special layers**: `gui_layer` (capslock hold) for window/desktop/tab/pane management, `omni_layer` for editing/file operations, `opts_layer` (tab hold), `apps_layer` (ralt), `bookmarks_layer` (prnt).

### Templates (templates.kbd)

Key templates used throughout:

- `t! th <tap> <hold>` — tap-hold with default timing
- `t! homerowmod` — fast-typing aware tap-hold for home row
- `t! type <key>` — typing with fast-typing detection
- `t! unmod_all <action>` — release all modifiers before action
- `t! toggle_layer`, `t! toggle_mod_layer`, `t! toggle_mod_2layer` — layer activation patterns
- `t! alt_char <letter>` — Spanish character composition (double-tap for accents)
- `t! 2x <action>` / `t! 3x <action>` — tap-dance for double/triple press

### Conventions

- Actions use the naming pattern: `action_<name>` in `actions.kbd`, `<app>_action_<name>` in app files.
- `~` **before `action_`** (`~action_tab_next`): reversed app priority in switch conditions — apps are checked in reverse order.
- Comments with `;;@autogen@` mark lines managed by the sync scripts — don't manually edit the switch conditions.
- `;; ""` is used because in nvim after a `[` the kanata comments `;;` won't dim. Using this hack, comments look good.
