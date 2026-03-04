# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A kanata (keyboard remapper for Linux) configuration with an **app-polymorphic action system** — the same key combo dispatches different actions depending on the active application (nvim, chrome, obsidian, tmux, etc.).

## Key Commands

```bash
# Sync all per-app action files with their shared app_*.kbd definitions (after editing app_*.kbd):
./scripts/kanata_sync_all_apps_interfaces.sh

# Sync a single per-app action file (dry-run, prints to stdout):
./scripts/kanata_sync_interfaces.py actions/chrome/chrome_omni.kbd
# Write mode:
./scripts/kanata_sync_interfaces.py -w actions/chrome/chrome_omni.kbd

# Regenerate kanata.kbd virtual keys + switch conditions (after adding/removing app files):
./scripts/kanata_sync_apps.py -f

# Reload kanata config, reload kwanata config, run kanata_sync_interfaces and kanata_sync_apps: RCtrl + k

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
  ├── templates.kbd           (reusable macros: homerowmod, tap-dance, layer toggles, etc.)
  ├── setup.kbd               (defsrc, default layer, homerow mod aliases, variable definitions)
  ├── bookmarks.kbd           (bookmark actions)
  ├── layers/
  │   ├── layer_windows.kbd       (GUI layers: windows, workspaces, tabs, etc.)
  │   ├── layer_omni.kbd          (domain layers: omni, apps, bookmarks, etc.)
  │   ├── layer_mod_key.kbd       (modifier layers: key-based)
  │   ├── layer_mod_physical.kbd  (modifier layers: physical keys)
  │   └── layer_*.kbd             (one per layer)
  ├── layers_toggle/
  │   ├── toggles_combined.kbd    (combined toggle definitions)
  │   ├── toggles_mod_gui.kbd
  │   ├── toggles_mod_key.kbd
  │   ├── toggles_mod_physical.kbd
  │   └── toggles_mod_special.kbd
  └── actions/
      ├── global_apps.kbd         (non-overridable: apps, apps_toggle, apps+0-9, apps+a-z)
      ├── global_windows.kbd      (non-overridable: window_*)
      ├── global_workspaces.kbd   (non-overridable: desktop_*, screen_*)
      ├── global_misc.kbd         (non-overridable: emojis, opts_restart_kwanata)
      ├── app_omni.kbd            (@autogen@ switch dispatch)
      ├── app_tabs.kbd
      ├── app_panes.kbd
      ├── app_groups.kbd          (contains ~ reversed actions)
      ├── app_*.kbd               (one per interface)
      ├── chrome/
      │   ├── chrome_omni.kbd
      │   ├── chrome_tabs.kbd
      │   └── ...
      ├── nvim/
      │   ├── nvim_omni.kbd
      │   ├── nvim_groups.1.kbd   (priority for ~ reversed actions)
      │   └── ...
      ├── ...
      ├── dolphin/
      ├── foot/
      ├── obsidian/
      ├── tmux/
      └── zellij/
```

### App-Polymorphism Pattern

Each app has a virtual key (`vk_<app>`) toggled by external software when the app gains/loses focus. Shared action files (`app_*.kbd`) use `(switch ;;@autogen@` to dispatch based on which virtual key is pressed:

```lisp
action_tab_next (t! unmod_all (switch ;;@autogen@
  ((input virtual vk_nvim)) $nvim_action_tab_next break
  ((input virtual vk_chrome)) $chrome_action_tab_next break
  () C-tab break   ;; default fallback
))
```

- **Priority**: Per-interface, controlled by the optional index in the per-app filename. `nvim_groups.1.kbd` (priority 1) beats `chrome_groups.4.kbd` (priority 4).
- **Reversed actions**: `~action_<name>` checks apps in reverse order, enabling alternate behavior when apps overlap (e.g. nvim inside tmux). The `~` prefix before `action_` reverses the app priority in switch conditions. Currently only in `app_groups.kbd`.
- App files can define **app variables** (e.g. `tmux_prefix A-b`) and **app-specific actions** not in the shared action file — both are preserved by the sync scripts. Extra vars go in the alphabetically-first per-app file.

### Sync Workflow

1. **Adding a new action**: Edit the relevant `app_*.kbd` file, add the action with `;;@autogen@` tag, then run `kanata_sync_all_apps_interfaces.sh` to propagate the placeholder to all per-app files.
2. **Adding a new app**: Create a subdirectory `actions/<app>/` with files `<app>_<name>.kbd` for each interface, then run `kanata_sync_apps.py -f` to register it in `kanata.kbd` and update switch conditions.
3. **Implementing an app action**: Uncomment the placeholder line in the per-app file (e.g. change `;;  tmux_action_tab_new` to `tmux_action_tab_new (macro $tmux_prefix c)`), then run `kanata_sync_apps.py -f` to wire it into the switch conditions.

### Layer System

- **Homerow mods**: `a/s/d/f/j/k/l/;` act as `lmet/lalt/lsft/lctl/lctl/rsft/lalt/lmet` when held, with fast-typing detection to prevent misfires.
- **Physical key remapping**: `lctl→lmet`, `lmet→lalt`, `lalt→lctl` (Mac-like `ctrl|alt|cmd` layout).
- **Modifier layers compose**: holding `lctl` activates `lctl_layer`; then holding `lalt` on top activates `lctl+lalt_layer`, etc. up to 3-modifier combos.
- **`!` prefix layers**: There are 2 sets of modifiers: homerow keys (lctl/lalt/lmet) and physical keyboard keys (!lctl/!lalt/!lmet). In normal apps they have the same functionality. In apps with a vim mode, you get 2 sets of functionality: one for vim-mode commands, the other for the app's own commands (e.g. obsidian, VS Code).
- **Special layers** (defined in layer\_\*.kbd files):
  - GUI layers: `windows_layer`, `workspaces_layer`, `tabs_layer`, `panes_layer`, `groups_layer`
  - Domain layers: `omni_layer` (caps hold), `opts_layer` (tab hold), `apps_layer` (ralt), `bookmarks_layer` (prnt), `num_layer`, etc.
  - Pane sublayers: `panes+move_layer`, `panes+resize_layer`, `panes+snap_layer`, `panes+swap_layer`

### Templates (templates.kbd)

Key templates used throughout:

- `t! th <tap> <hold>` — tap-hold with default timing
- `t! homerowmod` — fast-typing aware tap-hold for home row
- `t! type <key>` — typing with fast-typing detection
- `t! unmod_all <action>` — release all modifiers before action
- `t! toggle_layer`, `t! toggle_mod_layer`, `t! toggle_mod_2layer` — layer activation patterns
- `t! alt_char <letter>` — Spanish character composition (double-tap for accents)
- `t! 2x <action>` / `t! 3x <action>` — tap-dance for double/triple press
- `t! sft_switch <base> <lsft> <rsft>` — **DEPRECATED** (no longer used; replaced by layer variants)

### Conventions

- **Actions naming**: `action_<name>` in `app_*.kbd`, `<app>_action_<name>` in per-app files.
- **`~` prefix** (tilde before `action_`): `~action_tab_next` reverses app priority in switch conditions — apps are checked in reverse order. Allows alternate behavior when apps overlap (e.g. nvim inside tmux).
- **`!` prefix** has different meanings depending on context:
  - **Within action name** (`action_!lctl+a`): action triggered by physical lctl key (vs homerow mod)
  - **As layer prefix** (`!lctl_layer`, `!lalt_layer`, `!lmet_layer`): layer for physical modifier key (vs homerow mod)
- **Action variants**: Actions can have lsft/rsft variants using explicit naming:
  - Base: `action_new`
  - lsft variant: `action_lsft+new`
  - rsft variant: `action_rsft+new`
  - Example in combos: `action_lctl+t`, `action_lctl+lsft+t`, `action_lctl+rsft+t`
  - Variants are now distributed across layer variants (base_layer, base+lsft_layer, base+rsft_layer) instead of using sft_switch
- **`;;@autogen@` tag**: Marks lines managed by sync scripts — don't manually edit the switch conditions.
- **`;; ""`**: Vim fold markers (used because `;;` gets dimmed in nvim after `[`).
