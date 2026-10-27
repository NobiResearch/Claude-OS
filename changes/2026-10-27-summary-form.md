- The morning and board notifications are made by Claude OS itself ("Good morning — Tuesday,
  27 October"), not taken from the run's output, so a feed item can't write a notification that
  looks like the Mac's. Evolve's lines lose control and direction characters, and fall back to a
  fixed line if a backtick, `$`, a pipe or a web address is left.
