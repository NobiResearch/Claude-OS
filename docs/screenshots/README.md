# Screenshots

Everything here comes from `cos serve --demo`: a fictional Mac with made-up fixtures and a
scripted chat (`lib/cos/demo.py`). Never take one of your own Mac, and look at every frame
yourself before you push: the Guardian can't read images.

## How the tour GIF is made

Re-record it whenever the desktop changes enough that the GIF is out of date.

1. Run `bin/cos serve --demo --open` and size the browser window to 1440×900. Take
   screenshots at 2×, so 2880×1800.
2. Capture about ten frames, in this order, each on screen for about 2 seconds (0.7 s for
   the typing frames):
   1. the desktop with the empty chat;
   2. "Do I need to clean up my Mac?" being typed, then sent;
   3. Claude's answer with the table of safe targets;
   4. the Allow card for `bin/cos clean apply … --yes`;
   5. Storage, Updates, then Evolution's Board tab;
   6. Music, last. Its album art is Apple's: before this frame, replace every `.np-art` with
      a CSS gradient and remove the artwork images.
3. List the frames in `frames.txt`, one `file 'NN.png'` line and one `duration S` line for
   each, and end with the last file once more without a duration. Then:

   ```sh
   ffmpeg -f concat -safe 0 -i frames.txt \
     -vf "fps=10,scale=1200:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
     -loop 0 tour.gif
   ```

   That gives about 22 seconds and 700 KB. The menu bar shows the real time of recording.

   Check the menu bar's clock in every frame: it follows the browser's language, so set the
   browser to English, or the clock gives away where the recording was made.

## The two stills

`storage.png` and `evolve.png` are 1600×1000 at 1×, from the same demo server. Each has two
windows side by side: Vitals at the bottom left and Storage on the right, then Feeds at the
bottom left and Evolution's Board tab on the right. `COS.open(id)` opens a window, and setting
`COS.wins[id].el.style` left, top, width and height places it. Leave the Today panel's
suggestions uncovered.
