- **Runs that read feeds no longer get your own allow rules.** Your `.claude/settings.local.json`
  lets your terminal sessions use git, gh and more with no card. The morning brief, the weekly
  board and the app's chat don't load it any more:
  - in the app's chat, git, gh and `python3` now ask with a card;
  - the morning and board runs can't use git at all;
  - `cos ask` refuses inside the chat.

  Deny rules in that file, including a downloaded copy's, still apply. The chat also asks in
  the normal way whatever your global default mode is.
