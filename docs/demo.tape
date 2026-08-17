# VHS tape: real recording of reqverify running against the bundled coupon
# example, plus the pytest suite. Every command below actually executes —
# this is not a mockup. Install VHS (https://github.com/charmbracelet/vhs)
# and run `vhs docs/demo.tape` from the repo root to regenerate it.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1260
Set Height 1500
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 40ms

Hide
Type "cd /Users/myfolder/requirement-verification-agent && source .venv/bin/activate && clear"
Enter
Sleep 500ms
Show

Type "reqverify --help"
Enter
Sleep 3s

Type "reqverify evaluate requirements/coupon.md"
Enter
Wait+Screen@90s /FINAL:/
Sleep 3s

Type "clear"
Enter
Sleep 500ms

Type "pytest tests/ -q"
Enter
Wait+Screen@30s /passed/
Sleep 3s
