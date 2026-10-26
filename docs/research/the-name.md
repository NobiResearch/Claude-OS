# Can a downloadable app be called "Claude OS"?

- **Asked:** 2026-10-26, by the board (the Skeptic), before decision 0015 ships an app
- **Checked against:** Anthropic's trademark guidelines (effective 1 August 2024), searched on
  26 October 2026
- **Status:** open, and the human's call. Research only.

## Answer

Probably not without Anthropic's permission. "Claude" is Anthropic's trademark, and its
guidelines leave little room: anyone may use its trademarks "only as specifically permitted
by us and only in materials we approve beforehand", and not "in a manner that implies
Anthropic's sponsorship or endorsement, or a relationship or affiliation with Anthropic".
Permission can be withdrawn at any time. Nothing on that page allows "Claude" in a
third party's product or project name. A signed app called "Claude OS", in a GitHub
organization, with an orange diamond for a logo, can read as Anthropic's to a stranger, and that's
the use the guidelines rule out.

Saying what it works with is a different matter. "An operating layer for your Mac, built on
Claude Code" names Claude to describe compatibility, which is how projects usually refer to
the tools they build on. The README's notice ("not made or endorsed by Anthropic") helps, but
a notice doesn't make a name usable.

## Evidence

- **[Anthropic's trademark guidelines](https://www.anthropic.com/legal/trademark-guidelines):**
  use only as permitted and pre-approved, no implied endorsement or affiliation, and permission
  can be revoked. They say nothing specific about product names, nominative use or open source.
- **Branding guidance for Claude Code and the Agent SDK** (from third-party copies, not checked
  on anthropic.com):
  - "Claude Code" may not be part of another product's name, though a product may say it runs
    Claude Code;
  - Agent SDK products may use forms like "{YourAgentName} Powered by Claude";
  - wrappers of the Claude Code CLI, which Claude OS is, aren't addressed. A
    [request to clarify that](https://claudeissues.com/issue/24600-docs-branding-guidelines-should-address-third-party-projects-that-wrap-claude-co)
    was closed in March 2026.
- **Others with "Claude" in the name have met complaints:** one such project posted a
  [response to a trademark complaint](https://tacticremote.com/news/2026-03-27-response-to-trademark-complaint)
  in March 2026. Other tools rely on nominative fair use with a disclaimer, as
  [Gaugr](https://gaugr.app/en/fair-use) does.
- **The project the human compares Claude OS with** names itself after its own brand, not the
  model it runs on.

## Options

1. **Ask Anthropic first.** The guidelines name marketing@anthropic.com for brand questions.
   It's slow and uncertain, but it would settle it.
2. **A name of its own, "built on Claude Code" as the description.** It's the safest choice, and the name is the project's to
   keep. What a rename touches:
   - Visible: the app's name, the repository's name, the README and the docs.
   - Can stay, because nobody sees them: `~/.claude-os`, the `claude-os://` scheme, the
     bundle and App IDs (`app.claude-os.desktop`), and `cos`.
3. **Keep "Claude OS" for the source and pick another name for the downloadable app.** It
   splits the identity and still leaves the repository's name exposed.

## Recommendation

Decide before the first public release (0015 step 7), because every public thing added
under the current name (a release, a homepage, announcements) makes changing it dearer.
Option 2 is the one that doesn't depend on anyone's goodwill. Whichever it is, this is the
human's decision, and nothing has been renamed.
