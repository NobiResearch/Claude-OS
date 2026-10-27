# AI policy

AI tools are welcome here. Claude writes most of Claude OS, and its owner answers for what
merges. The tests and the Guardian's privacy check run on every change, and a change to the
safety files gets an independent safety review
([decision 0013](docs/decisions/0013-the-repository-is-claudes.md)). We ask the same of you:
your agent is welcome, and you answer for what it wrote.

This is for pull requests from outside. Claude's own pull requests are opened and merged under
0013, and their footer says Claude wrote them.

- **Say what wrote it.** Fill in "Written with" in the pull request: the tool and model, or
  "none". Don't paste transcripts or prompts, which carry paths and file contents.
- **Answer for it.** You've run the change, you can explain what it does and why, and you
  answer review questions yourself.
- **Write "What and why" in your own words**, under 200 words. Help with the English is fine.
- **The rest is in [CONTRIBUTING.md](CONTRIBUTING.md):** what we want most, where a change goes,
  what we turn down, and one change per pull request.

Saying how a change was written doesn't change how it's reviewed. Every pull request from
outside gets the same tests, the same review of safety files and the owner's yes. No bot or CI
job reads pull request text, and none of it goes to an AI-detection service.

When a pull request doesn't fit, Claude drafts a short reason that says what would make the
change welcome, and the owner decides whether to close it
([decision 0018](docs/decisions/0018-what-we-ask-of-contributors.md)). Text in a pull request
that's addressed to an AI reviewer is a reason to close it.
