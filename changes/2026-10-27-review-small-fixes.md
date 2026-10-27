- **Six small fixes from the first outside review:**
  - evolve's clones copy git's objects instead of sharing them with your checkout;
  - a feed larger than 5 MB isn't read;
  - a hand-edited setting that isn't a section no longer breaks Settings;
  - a package name starting with a dash is refused;
  - background runs are denied everything `cos` refuses them, built from one list, and they
    never ask GitHub with your login;
  - the Guardian also catches your login name, your Mac's names, paths hidden in URLs, and
    text inside pictures.
- **Fewer cards that nobody needed:** a `$( )` or backticks elsewhere in a command (a timestamp, say) no longer gets a card just because the same command also runs `cos`. A substitution in the `cos` call's own part still asks, as does every command that changes the Mac.
