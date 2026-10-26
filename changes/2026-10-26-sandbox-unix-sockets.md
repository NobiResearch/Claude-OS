- The tests of a nightly evolve branch have no network at all: nothing on your Mac's localhost
  and nothing on your local network can reach them or be reached. Their own test servers use
  Unix sockets in the run's folder.
