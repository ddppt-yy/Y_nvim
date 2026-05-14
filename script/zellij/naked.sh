zellij action dump-layout >  ~/.config/zellij/current.kdl
python3 ~/.config/zellij/parse_focused_tab.py nake >  ~/.config/zellij/new.kdl
zellij action override-layout ~/.config/zellij/new.kdl --retain-existing-terminal-panes --apply-only-to-active-tab
zellij action toggle-pane-frames
/bin/rm -rf  ~/.config/zellij/current.kdl ~/.config/zellij/new.kdl
