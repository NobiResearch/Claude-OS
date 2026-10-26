- `cos status` reads the load, swap and top processes correctly with a Norwegian (or any
  decimal-comma) locale; before, it showed no top processes and a wrong load average.
- Tools that live inside an app bundle (git inside Xcode.app) keep their own name in top
  processes, and a group's memory shows as approximate (≈), since shared pages count twice.
