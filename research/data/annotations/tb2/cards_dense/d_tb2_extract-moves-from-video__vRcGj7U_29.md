# Annotation card `d_tb2_extract-moves-from-video__vRcGj7U_29`

- corpus: `tb2`
- task id: `extract-moves-from-video`
- scaffold: `terminus-3-3`   model: `gemini-3.1-pro-preview@Google`
- trajectory length: 105 steps   final task reward: 0
- **window under judgement: steps 20–29 (w=10)**
- sampling note: dense position sample (stratified by scaffold and outcome)

## Task statement (all the information the agent was given)
```text
Download this video of someone playing zork. https://www.youtube.com/watch?v=ZCbvyPbhRfA. Then transcribe the entire contents of the text, and create a file /app/solution.txt that has all the moves they input, one per line, in the format 'n' or 'get bag' etc.
```

## Before the window (steps 6–19)
```text
[  6] execute:ffprobe | execute:ffmpeg  obs="$37"
[  7] read:read(app/frame_10s.png)  obs="File Read Result for '/app/frame_10s.png': { "layout_description": "The image shows a classic text adventure game interface, specifically Zo"
[  8] execute:$38  obs="$39"
[  9] other:shell  obs="New Terminal Output: "
[ 10] other:shell  obs="New Terminal Output: "
[ 11] other:shell  obs="New Terminal Output: "
[ 12] other:shell  obs="New Terminal Output: "
[ 13] execute: | read:wc(raw_commands.txt) | read:tail(raw_commands.txt) | execute:fg  obs="Previous response had warnings: WARNINGS: - Command 1 should end with newline when followed by another command. Otherwise the two commands w"
[ 14] execute: | control:kill | edit:cat(extract_moves.py,raw_commands.txt) | execute:python3(extract_moves.py)  obs="$3a"
[ 15] other:shell  obs="New Terminal Output: Processed frame 15 Processed frame 30 Processed frame 45 Processed frame 60 Processed frame 75 Processed frame 90 Proce"
[ 16] execute: | read:cat(raw_commands.txt) | control:kill  obs="Previous response had warnings: WARNINGS: - Command 1 should end with newline when followed by another command. Otherwise the two commands w"
[ 17] execute:$3b  obs="$3c"
[ 18] other:shell  obs="New Terminal Output: Large change at frame 330, prev cmds: >n Large change at frame 360, prev cmds: >u Large change at frame 390, prev cmds:"
[ 19] other:shell  obs="New Terminal Output: Large change at frame 420, prev cmds: >. Large change at frame 435, prev cmds: > Large change at frame 465, prev cmds: "
```

## WINDOW UNDER JUDGEMENT (steps 20–29)
```text
[ 20] other:shell  obs="New Terminal Output: Large change at frame 510, prev cmds: >move rug Large change at frame 540, prev cmds: >open tra Large change at frame 570, prev cmds: >d Large change at frame 585, prev cmds: >light lamp "
[ 21] other:shell  obs="New Terminal Output: Large change at frame 585, prev cmds: >light lamp Large change at frame 600, prev cmds: >e Large change at frame 615, prev cmds: >get Large change at frame 630, prev cmds: >n Large change at frame 660, prev cmds: >slay trol "
[ 22] execute: | control:kill | execute:$3d  obs="$3e"
[ 23] other:shell  obs="$3f"
[ 24] other:shell  obs="New Terminal Output: Frame 380: get eg Frame 415: open Frame 450: get all_ Frame 500: open cas_ "
[ 25] other:shell  obs="New Terminal Output: Frame 500: open cas_ Frame 530: move rug Frame 565: light lamp Frame 595: Frame 645: slay trol "
[ 26] other:shell  obs="New Terminal Output: Frame 675: Frame 705: e Frame 740: SW, Frame 785: ulyss "
[ 27] other:shell  obs="New Terminal Output: Frame 850: put all but lamp_ Frame 880: Frame 910: temple_ Frame 950: open solid_ Frame 980: get sharp_ "
[ 28] other:shell  obs="New Terminal Output: Frame 980: get sharp_ Frame 1010: s Frame 1040: Frame 1070: w Frame 1100: put solid Frame 1155: open trap Frame 1185: d. Frame 1215: Frame 1250: push al Frame 1285: get tool "
[ 29] other:shell  obs="New Terminal Output: Frame 1320: s. Frame 1350: set nut_ Frame 1380: Frame 1415: u "
```

## After the window (steps 30–43)
```text
[ 30] other:shell  obs="New Terminal Output: Frame 1415: u Frame 1445: drop bo_ Frame 1475: Frame 1505: s, Frame 1540: s "
[ 31] other:shell  obs="New Terminal Output: Frame 1540: s Frame 1570: pump Frame 1655: put all but lamp,pump Frame 1710: def late boat Frame 1740: Frame 1770: get "
[ 32] execute: | control:kill | execute:$40  obs="$41"
[ 33] execute:$42  obs="$43"
[ 34] other:shell  obs="New Terminal Output: Found 127 command frames. Saved commands_0.png Saved commands_1.png Saved commands_2.png Saved commands_3.png root@8ada"
[ 35] read:read(app/commands_0.png)  obs="File Read Result for '/app/commands_0.png': [ "n", "u", "get eg", "open", "get all", "open cas", "open trap", "light lamp", "", "slay trol","
[ 36] execute:$44  obs="$45"
[ 37] other:shell  obs="New Terminal Output: Found 112 scroll frames. Frame 25: ['>'] Frame 340: ['>'] "
[ 38] execute: | control:kill | execute:$46  obs="$47"
[ 39] execute: | control:kill | execute:$48  obs="$49"
[ 40] other:shell  obs="New Terminal Output: "
[ 41] other:shell  obs="New Terminal Output: "
[ 42] other:shell  obs="New Terminal Output: "
[ 43] execute: | read:cat(app/solution.txt) | execute:fg  obs="Previous response had warnings: WARNINGS: - Command 1 should end with newline when followed by another command. Otherwise the two commands w"
```

## Final steps of the trajectory
```text
[ 99] other:shell  obs="New Terminal Output: 4__' "
[100] other:shell  obs="New Terminal Output: 5__' "
[101] no-tool  say="{ "analysis": "Requirements Checklist:\n1. Download the video of Zork gameplay from https://www.youtube.com/watch?v=ZCbv"  obs="Previous response had parsing errors: ERROR: Command 1 missing required 'keystrokes' field Please fix these issues and provide a proper JSON response."
[102] other:shell  obs="New Terminal Output: 6__' "
[103] other:shell  obs="New Terminal Output: 7__' "
[104] other:shell  obs="New Terminal Output: 8__' "
```

## Your label

Apply `docs/annotation_guide.md` §4 in order. Record:

```
label: PRODUCTIVE | STAGNANT | REGRESSION | DONE_REDUNDANT | BLOCKED_EXTERNAL | UNCERTAIN
confidence: high | medium | low
boundary: true | false        (window cuts a productive interval in half)
channels_advanced: E | I | V | none
justification: one or two sentences citing specific step numbers
```