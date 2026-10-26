- The weather alert in the boot banner, `cos status` and `cos weather` no longer warns about
  an hour that's already over ("Rain likely around 02:00" at 03:30). A cached forecast drops
  the hours that have passed and works the alert out again from the ones still to come.
