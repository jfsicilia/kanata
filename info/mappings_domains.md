# Domain mappings (spc + key)

Hold **`spc`** to open `domains_layer`. Press a key to enter its **sub-domain**
(`domains+<key>_layer`); the popup help then shows the actions available inside
it. Repeating the domain key runs that sub-domain's default action; extra keys
pick more specific ones.

Everything here is app-specific: the **Apps** column lists which apps implement
the sub-domain today. `—` = the sub-domain exists but no app fills it yet.
Anything not in this table (`` ` ``, `-`, `=`, `0`–`9`) is a reserved
placeholder with no action.

`$toggle` = the toggle key (physical `ralt`), `$search` = the search key
(physical `!lalt`).

| spc+ | Sub-domain     | Inner keys                                                                                        | Apps                                                                      |
| ---- | -------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| a    | Actions        | `a`                                                                                               | nvim                                                                      |
| b    | Bookmarks      | `b`                                                                                               | nvim, obsidian                                                            |
| c    | Calendar       | `c` · `d` day · `y` daily                                                                         | obsidian                                                                  |
| d    | Definitions    | `d` · `s` source                                                                                  | nvim                                                                      |
| e    | Explorer       | `e` · `f` find/focus · `r` recents                                                                | dolphin, nvim, obsidian                                                   |
| f    | Filter         | `f`                                                                                               | —                                                                         |
| g    | Git            | `g` · `l` lazygit                                                                                 | foot, nvim                                                                |
| h    | Hyperlinks     | `h` · `o` outline                                                                                 | nvim, obsidian                                                            |
| i    | Info           | `i`                                                                                               | dolphin                                                                   |
| j    | Jumps          | `j`                                                                                               | nvim                                                                      |
| k    | Keymaps        | `k`                                                                                               | chrome, dolphin, firefox, nvim, tmux                                      |
| l    | Locations      | `l`                                                                                               | nvim                                                                      |
| m    | Mem            | `m` clipboard history                                                                             | global (`M-v`)                                                            |
| n    | Notebooks      | `n`                                                                                               | —                                                                         |
| o    | Output         | `o`                                                                                               | —                                                                         |
| p    | Properties     | `p` · `a` all                                                                                     | obsidian                                                                  |
| q    | Quickfix       | `q`                                                                                               | nvim                                                                      |
| r    | References     | `r` · `i` incoming · `o` outgoing · `s` source                                                    | nvim                                                                      |
| s    | Symbols        | `s` · `w` workspace                                                                               | nvim, obsidian                                                            |
| t    | Terminal       | `t` · `$toggle` toggle terminal                                                                   | dolphin, nvim                                                             |
| u    | UI             | `u` · `g` graph                                                                                   | obsidian                                                                  |
| v    | Virtualization | `v`                                                                                               | —                                                                         |
| w    | Warnings       | `w`                                                                                               | —                                                                         |
| x    | Extensions     | `x`                                                                                               | —                                                                         |
| y    | History        | `y` · `;` commands · `$search` history search                                                     | nvim                                                                      |
| z    | Tests          | `z`                                                                                               | —                                                                         |
| ;    | Commands       | `;`                                                                                               | colab, nvim, obsidian, tmux                                               |
| '    | Registries     | `'`                                                                                               | nvim                                                                      |
| ,    | Settings       | `,` · `r` reload                                                                                  | chrome, dolphin, firefox, nvim, obsidian, whatsapp, zapzap · reload: tmux |
| .    | Tags           | `.`                                                                                               | dolphin, nvim                                                             |
| /    | Help           | `/` · `k` → bare layer                                                                            | dolphin, nvim                                                             |
| \    | Compare        | `\` files (shift: folders) · `j`/`k` next/prev · `o` obtain · `p` push                            | foot, nvim                                                                |
| [    | Backlinks      | `[`                                                                                               | obsidian                                                                  |
| ]    | Outlinks       | `]` · `a` all                                                                                     | obsidian                                                                  |
| omni | AI (Sidekick)  | `omni` · `a` agent · `c` Claude · `s` send selection · `f` send file · `p` prompt · `d` close CLI | nvim                                                                      |

> Not a domain: the first-class GUI citizens (windows, workspaces, panes, tabs,
> sessions, agents, worktrees) each have their own hold key — see the header of
> `setup.kbd`. A _domain_ is only the `spc+` system.
