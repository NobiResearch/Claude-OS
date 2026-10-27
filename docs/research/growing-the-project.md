# How could Claude OS grow the way Hermes Agent did?

- **Asked:** 2026-10-27, overnight lab (three scouts: how Hermes Agent grew; what drives stars
  and contributors; getting a Mac app to people who don't code)
- **Checked against:** GitHub's API, Hacker News's Algolia API, published studies, and other
  projects' own files, all read on 27 October 2026
- **Status:** research only. Every step that posts somewhere public or changes the
  repository's settings is the human's call.

## Answer

Most of Hermes Agent's reach came from things Claude OS doesn't have:
- a known AI lab behind it;
- a 147,000-member Discord that existed before the project;
- a funded, full-time team;
- being ready when OpenClaw was cut off from Claude Code subscriptions in April 2026.

What Claude OS can copy is the way the project is shaped:
- **Outside work goes to the edges.** Contributors add skills and one-file plugin catalog
  entries rather than changing the core.
- **Contributors keep their names.** Authorship survives into `main` and into the release
  notes.
- **It ships so often that forks fall behind.** That keeps people building on the original.

The research on launches agrees. A good Show HN brings a few hundred stars, and about 92% of
that is gone within 48 hours. Users who stay come from being easy to find where Claude Code
users already look, and from a tool people keep using.

Stars rarely become contributors: one Claude Code plugin has about 306,000 stars and 44
contributors. What turns a newcomer into a contributor is:
- a human reply within a day;
- work that is clearly scoped;
- a written AI policy.

For people who don't code, the Mac apps that compare to Claude OS ship a notarized download
on GitHub Releases, offer a Homebrew cask, and install their updates from inside the app.
Claude OS's once-a-day link to the download is the odd one out. That's fine for a first
release, but worth revisiting.

Two things come before any launch:
- **The name.** Renaming in the middle of a launch costs the most.
- **A trust story.** In 2026, agent tools are judged on security first.

## Recommendations

In order. Items marked **(the human)** post publicly or change settings, so they're the
human's call.

1. **Settle the name (the human).** "Claude" in the name likely needs Anthropic's OK (see
   [the-name.md](the-name.md)). It also blocks or holds a listing in Anthropic's plugin
   directory. Anthropic made Clawdbot rename at the height of its virality, and scammers took
   the old handle during the switch.
2. **Make it one step to try, and show it moving.**
   - **The step:** the signed app (0015) or a one-line install. Today the README asks for a
     clone, then `bin/cos install`, and the app has to be built.
   - **The clip:** a 20–60 second clip at the top of the README, such as the tour GIF waiting
     on a local branch.
   - Show HN's own rules ask for something people can try "without barriers".
3. **Put trust first in the README.** Write a short threat model in plain words:
   - Claude OS is read-only by default, and `--yes` is needed for any change;
   - every change goes in the journal;
   - it never asks for Full Disk Access or Accessibility;
   - the night shift is opt-in, and off in a downloaded copy;
   - feed and pull request text are treated as data, never as instructions;
   - say what merges on its own, and what doesn't.
4. **Give contributors a lane outside the core.**
   - **A community skills catalog.** One pull request adds one `catalog/<name>.yaml` that pins a
     repository to an exact commit, and `cos` installs it. Hermes's catalog has 860 entries,
     and its release notes credit 400+ plugin authors.
   - **Rules from day one:** a human merges every entry; no self-updating; capabilities
     declared up front; no patching the core.
   - **First:** it needs the board and 0017 (settings that are safe for strangers). An installed
     skill is code that Claude runs.
5. **Credit every contributor.**
   - A squash merge of someone's own pull request keeps their work under their name. The risk is
     a maintainer finishing that work in a new pull request. Then:
     - add their `Co-authored-by:` trailer;
     - tell them on the original: "merged via #N, under your name".
   - Name contributors by handle in each release's notes.
6. **Write down what we want, and our AI policy.**
   - **In CONTRIBUTING.md:**
     - a ranked list of the work we want most;
     - a "skill, syscall or daemon?" guide;
     - a list of what we turn down even when it's well built.
   - **In an `AI_POLICY.md`:** say which tool wrote the change; a human understands every line;
     one change per pull request; a summary written by a human. Ghostty and superpowers work
     this way.
   - Hermes's rubric also steers its triage bot. Claude OS will get mostly agent-written pull
     requests, so it needs the same.
7. **Reply to every first issue or pull request within a day.** Claude can draft the reply in a
   session with the human. Don't add a CI reviewer that reads untrusted pull request text while
   holding tokens (see "PromptPwnd" below).
8. **Be listed where Claude Code users look (the human).**
   - **awesome-claude-code:** eligible from about 7 November, when the repository is 14 days
     old. It takes submissions only through a web form, filled in by a person.
   - **Anthropic's community plugin directory:** once the name is settled.
9. **Launch once, deliberately, in the human's voice (the human).**
   - First a personal "why and how" post. That's how superpowers grew, after Simon Willison
     picked up its author's post.
   - Then a Show HN on a weekday between 12:00 and 17:00 UTC, with the human answering in the
     thread for hours. Expect about 100–300 stars, and plan for the weeks after.
10. **Make the first release easy to trust and to update.**
    - **Before it (the human):**
      - turn on immutable releases;
      - publish as draft, then upload, then publish;
      - put the zip's SHA-256, the commit and the expected `spctl -a -vv` output in the
        notes.
    - **Updates:** keep the once-a-day link for v1. The update card could link straight to the
      zip.
    - **Sparkle** (updates installed after a click, never on their own) goes back to the board
      when friction shows downloads falling behind, or by the second or third release. It
      reverses 0015's "no app that replaces itself".
    - **Homebrew:**
      - **Now:** a tap of our own (creating it is the human's call).
      - **After 23 November, with 75+ stars:** Homebrew's main repository, submitted by someone
        other than the owner.
    - **Add to the release check in a second account:** does a clone made by the downloaded app
      come out quarantined, and does `bin/cos` still run?
11. **Give contributors a place to talk (the human).**
    - Turn on GitHub Discussions: 10 of 12 Claude Code projects checked have it on. Open a
      Discord later.
    - Seed 5–10 scoped good first issues from the generic friction log. Four drafts are
      waiting.

**Never:**
- buy stars;
- post AI-written comments on Hacker News (HN bans them);
- let an agent with write tokens read untrusted issue or pull request text in CI;
- open the core to pull requests before the edge lane exists. Hermes Agent has 34,000 open
  pull requests and posts about the backlog: volume isn't health.

## Evidence

### How Hermes Agent grew

From GitHub's API, 27 October 2026, unless marked otherwise.

- **Size:**
  - 257,456 stars, 56,419 forks and 986 watchers;
  - MIT license, written in Python;
  - 107,268 pull requests ever: 19,597 merged and 34,010 open;
  - about 657 merged in the week to 27 October, 217 of them by a co-founder. (verified)
- **Going public:**
  - The repository was created in July 2025 and went public around 25 February 2026. Its issue
    #100 is from 27 February, #1,000 from 12 March and #100,000 from 1 September. (verified)
  - Nous's own note confirms an MIT release "this past February". (verified)
- **Releases:**
  - 44 releases from 12 March to 23 October;
  - eight in the first month, then roughly every one or two weeks;
  - major releases get names. (verified)
- **Stars over time:** a community tracker's own counts:
  - 22,000 on 11 March;
  - 57,200 on 11 April;
  - 165,033 on 24 May;
  - 246,755 on 18 September.
  
  (unverified; TechCrunch's "roughly 214,000" on 13 July fits)
- **The biggest outside event:**
  - "Anthropic no longer allowing Claude Code subscriptions to use OpenClaw" reached 1,099
    points on Hacker News on 3 April 2026. (verified)
  - Hermes already had a command to move over from OpenClaw.
  - The steepest climb, +108,000 stars between 11 April and 24 May, comes right after.
  - The timing fits, but whether it caused the climb is unverified.
- **Hacker News wasn't the driver:**
  - The project's own HN post got 4 points.
  - Its best HN story ever got 52. (verified)
- **README:**
  - **Since launch day:** a banner, badges, one bold sentence, a feature table and a
    `curl | bash` install.
  - **No** GIF or video.
  - **Later additions:** Homebrew, Docker, Nix, Windows and Android installs.
  
  (verified)
- **Contributor on-ramp:**
  - **CONTRIBUTING.md** (1,039 lines) opens with:
    - a ranked list of priorities;
    - "search first", with the exact commands to run;
    - "should it be a skill or a tool?" ("almost always skill").
  - **The contributing guide** adds a list of what's "rejected even when well-built", and a
    ladder for where a change belongs, from extending existing code down to a new core tool as
    a last resort.
  - **AGENTS.md** sets the rubric its triage bot follows. The bot may close an issue only as
    already fixed, can't reproduce, or incoherent.
  
  (verified)
- **No "good first issue" label.** Its labels are a triage system instead: by area, component,
  platform and priority. A weekly bot files issues that group Discord support threads.
  (verified)
- **The plugin catalog:**
  - one `plugin-catalog/<name>.yaml` per plugin, pinned to a 40-character commit hash, with 860
    entries;
  - a human merges each one;
  - plugins may not update themselves or patch the core, and must declare what they can do;
  - a plugin that needs more asks for a wider plugin interface instead.
  
  (verified)
- **Credit:**
  - When maintainers finish a contributor's pull request, they cherry-pick it so the commit
    keeps its author. Then they comment on the original: "Merged via #144910. @… commit is on
    main unchanged and under their name."
  - A CI check maps every commit email to a GitHub login.
  - Each release names its core team, top community contributors and all contributors.
  
  (verified)
- **Things Claude OS can't copy:**
  - the Nous Research Discord: 147,207 members, older than the project (verified);
  - a funded team;
  - endorsement from well-known people (named by the community tracker; unverified).

### What drives stars and contributors

- **Show HN, 188,000 posts from 2012 to April 2026:**
  - the median score is 2;
  - 50 points puts a post in about the top 6%;
  - a post gets about 1.4 stars per point;
  - about 92% of the effect is gone after 48 hours;
  - score explains only about 8% of the difference in stars.
  
  [Blog analysis](https://danfking.github.io/blog/2026/04/23/show-hn-by-the-numbers/)
  (verified; its star counts are capped)
- **138 AI repositories launched on HN:** on average 121 stars in 24 hours and 289 in 7 days,
  with much lower medians. Posting between 12:00 and 17:00 UTC helped; the "Show HN" tag
  didn't. [arXiv 2511.04453](https://arxiv.org/html/2511.04453v1) (verified; small sample)
- **HN's rules now:**
  - Show HN has been restricted for new accounts since about March 2026 ("we got flooded, and
    still are");
  - AI-generated or AI-edited comments are banned;
  - you must be "around to discuss" your post;
  - asking friends to upvote isn't allowed.
  
  [showlim](https://news.ycombinator.com/showlim), [Show HN rules](https://news.ycombinator.com/showhn.html)
  (verified)
- **Launch spikes are small next to lifetime use.** Among the top 5,000 repositories, the
  median got 7% of its stars in its first four weeks. Three in four developers check stars
  before they use or contribute. [arXiv 1811.07643](https://arxiv.org/pdf/1811.07643)
  (verified; biased toward successful projects)
- **Twitter/X:** across 44,544 tweets about 2,370 repositories, tweets raised stars about 7% but
  contributors only about 2%. Tweets from fans worked better than the authors' own. (from
  press coverage of an ICSE 2022 paper, not the paper itself)
- **Stars against contributors**, from GitHub's API on 27 October 2026:

  | Project | Stars | Contributors (about) |
  |---|---|---|
  | superpowers | 305,696 | 44 |
  | claude-mem | 103,476 | 309 |
  | get-shit-done | 64,213 | 144 |
  | OpenClaw | 393,165 | 3,698 |

  (verified)
- **A fast first reply helps.** Across 111,000 pull requests in 10 projects, newcomers whose
  first human reply came within a day were more likely to contribute again: a median of 15%
  more, relative. [arXiv 2304.08426](https://arxiv.org/pdf/2304.08426) (verified; correlation)
- **Good first issues are weakening.** Newcomers still take about 27% of them, but their merge
  rate fell from 62% to 42% after January 2024. The authors suspect AI spam.
  [arXiv 2604.27532](https://arxiv.org/html/2604.27532v2) (verified)
- **AI-written pull requests:**
  - Maintainers estimate 25% of incoming pull requests are low-quality AI output.
    [Linux Foundation, 20 October 2026](https://www.linuxfoundation.org/press/new-lf-research-survey-shows-generative-ai-cuts-open-source-coding-time-in-half-but-25-of-incoming-pull-requests-are-considered-ai-slop)
    (verified; based on what maintainers perceive)
  - Ghostty's AI_POLICY.md asks contributors to disclose AI use and to understand every line.
    (verified)
  - superpowers assumes an agent wrote each pull request and asks for a human-written summary
    of under 200 words. (verified)
- **Some places are closing to AI-built projects:**
  - Codeberg banned projects that are largely LLM-generated, by a vote of 358 to 144.
    [Hackaday](https://hackaday.com/2026/07/24/codeberg-bans-cryptocurrency-and-llm-generated-code-projects/)
    (verified)
  - r/opensource reportedly removes them. (one secondary source; unverified)
- **"PromptPwnd":** untrusted issue or pull request text reaches an agent running in CI with
  privileged tokens, and secrets leak.
  [Aikido](https://www.aikido.dev/blog/promptpwnd-github-actions-ai-agents) (verified)
- **Skills are a security target.** Snyk checked 3,984 public skills: 13.4% had critical issues,
  and 76 were confirmed malicious.
  [Snyk](https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub) (verified)
  - A catalog for Claude OS would need the Guardian's scan and a commit pin from day one.
- **Fake stars:** about 6 million suspected fake stars across 18,600 repositories. They help for
  under about two months, then become a liability.
  [ICSE 2026](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/14/Six-Million-Suspected-Fake-Stars-on-GitHub-A-Growing-Spiral-of-Popularity-Contests)
  (partly verified)
- **Where Claude Code users look:**
  - **Anthropic's community plugin directory** takes submissions through a portal. It blocks
    `claude` as a whole name and holds names that look official for review. `claude-os` is
    reserved. [Submitting](https://claude.com/docs/plugins/submit) (verified)
  - **awesome-claude-code** (56,600 stars) lists a project once it's 14 days old with active
    development, or has 100 stars. Submissions go through a web form, filled in by a person.
    (verified)

### Getting a Mac app to people who don't code

- **Open-source Mac apps:** all six checked keep their downloads on GitHub Releases and have a
  Homebrew cask (Rectangle, Stats, MonitorControl, AltTab, Maccy, Ice).
  - **Updates:** four update through Sparkle 2, with a version feed and signed archives.
    Stats wrote its own updater, and its 2026 commits fix by hand the edge cases Sparkle
    already handles. (verified in their files)
  - **Sparkle needs keeping current:** CVE-2025-0509, a bypass of its signature check, was
    fixed in 2.6.4. (verified via a secondary listing)
- **Local AI desktop apps** (Goose, Jan, Hermes Agent's app, LM Studio, Ollama, Claude) all
  install their updates from inside the app. (verified in docs and casks)
  - Their command-line installs use `curl | bash` and run into problems with Terminal and PATH.
  - A once-a-day link to the download, as Claude OS has now (0015), makes it the odd one out.
  - Because a downloaded copy's code follows its app, someone who never drags in the new app
    also stays on old code.
- **Hermes Agent is the closest design to Claude OS.**
  - Its installer clones the code into the home folder.
  - It installs Python, Node, ripgrep and FFmpeg, plus Chromium and a computer-use driver unless
    you opt out.
  - It updates by following git.
  
  [Install docs](https://hermes-agent.nousresearch.com/docs/getting-started/installation/)
  (verified)
- **Claude Code:**
  - It installs with `curl … | bash` and updates itself.
  - Its Homebrew casks don't update themselves.
  - It needs a paid plan.
  
  [Setup](https://code.claude.com/docs/en/setup) (verified)
- **OpenClaw is the cautionary tale.** 341 of 2,857 skills in its marketplace were malicious,
  most of them installing a macOS password stealer through fake "prerequisites" the user was
  told to run.
  [The Hacker News](https://thehackernews.com/2026/02/researchers-find-341-malicious-clawhub.html)
  (secondary report, verified)
- **Homebrew's main cask repository** isn't open to Claude OS yet.
  - It wants at least 75 stars, 30 forks or 30 watchers. If the owner submits it themselves, the
    bar is 225, 90 or 90.
  - It normally turns down repositories less than 30 days old.
  - [Acceptance policy](https://github.com/Homebrew/brew/blob/main/docs/Package-Acceptance-Policy.md)
    (verified)
- **A tap of our own works today.**
  - Homebrew 6 makes you trust a third-party tap, but `brew install --cask owner/tap/name` trusts
    just that one cask. [Tap trust](https://github.com/Homebrew/brew/blob/main/docs/Tap-Trust.md)
    (verified)
  - Nothing in Homebrew's policy rules out an app that downloads its code on first launch.
    (verified)
  - The cask should leave `auto_updates` off, because the app only links to new versions. Then
    a plain `brew upgrade` upgrades it. (Cask Cookbook, verified)
  - Claude OS's app is built for Apple silicon only, so the cask needs `depends_on arch: :arm64`.
    (verified in `app/build.sh`)
- **Trust signals:**
  - **Notarization** "is not App Review", only an automated malware and signing scan. Since
    macOS Sequoia, Control-click no longer gets around Gatekeeper, so for people who don't code
    a notarized app is the baseline.
    [Apple](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
    (verified)
  - **GitHub's immutable releases** lock a release's tag and files and attest them, checked with
    `gh release verify`. They need no CI, so they fit "built only on the maintainer's Mac".
    [GitHub docs](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases)
    (verified)
- **Quarantine:** a clone made in Terminal carries no quarantine flag. Whether a clone made by
  the notarized, quarantined app does is untested. (verified for Terminal only)

## What Claude OS already has

As of 27 October 2026:

- **In place:**
  - CONTRIBUTING.md, AGENTS.md and SECURITY.md;
  - issue templates for bugs and ideas, and a pull request template;
  - the MIT license;
  - a demo mode for screenshots;
  - the Guardian on every commit;
  - a README that opens with what Claude OS does.
- **Missing:**
  - an AI policy;
  - a ranked list of wanted work;
  - a lane outside the core;
  - Discussions (off);
  - a one-step install, since the signed app (0015) isn't released yet.

## Open questions

- Whether the human's Hacker News account would pass the Show HN limits.
- Whether "built by Claude, for Claude" helps (with Claude Code users) or hurts (on HN and
  general open-source sites) more. It probably splits by audience; untested.
- No study measures GIFs, one-line installs, Product Hunt or Discord against stars.
- Whether Hermes Agent's climb in April and May came from the OpenClaw news; the timing fits.
- How Anthropic's directory scan treats skills that call a Python CLI.
- How often people skip updates that only link to a download. There's no data, only that every
  AI desktop app checked updates from inside the app.
- Whether Homebrew's reviewers would object to a third party's cask name starting with "claude".
