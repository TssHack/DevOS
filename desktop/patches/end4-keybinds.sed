# DESK-021: the one change DevOS makes to end-4's own files.
# Super+A opens the DevOS AI panel instead of end-4's left sidebar (which has its
# own AI chat). The end-4 sidebar stays on Super+B and Super+O.
# A custom/*.lua bind cannot replace it: both bindings would fire.
s|^hl.bind("SUPER + A", hl.dsp.global("quickshell:sidebarLeftToggle"), { description = "Shell: Toggle left sidebar" })$|hl.bind("SUPER + A", hl.dsp.global("devos:aiToggle"), { description = "DevOS AI" })|
