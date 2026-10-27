- The nightly evolve run stays in its sandbox: it runs no hooks (a hook runs outside the
  sandbox, and the run could have edited the code its hooks call), and its file edits are
  limited to its own workspace.
