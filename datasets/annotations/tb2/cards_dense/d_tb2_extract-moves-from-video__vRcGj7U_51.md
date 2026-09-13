# Annotation card `d_tb2_extract-moves-from-video__vRcGj7U_51`

- corpus: `tb2`
- task id: `extract-moves-from-video`
- scaffold: `terminus-3-3`   model: `gemini-3.1-pro-preview@Google`
- trajectory length: 105 steps   final task reward: 0
- **window under judgement: steps 42–51 (w=10)**
- sampling note: dense position sample (stratified by scaffold and outcome)

## Task statement (all the information the agent was given)
```text
Download this video of someone playing zork. https://www.youtube.com/watch?v=ZCbvyPbhRfA. Then transcribe the entire contents of the text, and create a file /app/solution.txt that has all the moves they input, one per line, in the format 'n' or 'get bag' etc.
```

## Before the window (steps 28–41)
```text
[ 28] other:shell  obs="New Terminal Output: Frame 980: get sharp_ Frame 1010: s Frame 1040: Frame 1070: w Frame 1100: put solid Frame 1155: open trap Frame 1185: d"
[ 29] other:shell  obs="New Terminal Output: Frame 1320: s. Frame 1350: set nut_ Frame 1380: Frame 1415: u "
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
```

## WINDOW UNDER JUDGEMENT (steps 42–51)
```text
[ 42] other:shell  obs="New Terminal Output: "
[ 43] execute: | read:cat(app/solution.txt) | execute:fg  obs="Previous response had warnings: WARNINGS: - Command 1 should end with newline when followed by another command. Otherwise the two commands will be concatenated together on the same line. New Terminal Output: ^Z [1]+ Stopped python3 sequence_align_ocr.py root@8adacdf9-45a9-4334-9496-c4410a45d812:/app"
[ 44] other:shell  obs="New Terminal Output: "
[ 45] other:shell  obs="New Terminal Output: "
[ 46] other:shell  obs="New Terminal Output: "
[ 47] other:shell  obs="New Terminal Output: "
[ 48] execute: | search:grep | execute:fg  obs="$4a"
[ 49] execute: | search:grep | execute:fg  obs="$4b"
[ 50] other:shell  obs="New Terminal Output: "
[ 51] other:shell  obs="New Terminal Output: "
```

## After the window (steps 52–65)
```text
[ 52] other:shell  obs="New Terminal Output: "
[ 53] execute: | search:grep | execute:fg  obs="$4c"
[ 54] other:shell  obs="New Terminal Output: "
[ 55] other:shell  obs="New Terminal Output: "
[ 56] other:shell  obs="New Terminal Output: "
[ 57] execute: | control:kill | execute:$4d  obs="$4e"
[ 58] execute:$4f  obs="$50"
[ 59] other:shell  obs="New Terminal Output: "
[ 60] other:shell  obs="New Terminal Output: "
[ 61] other:shell  obs="New Terminal Output: "
[ 62] execute: | search:grep | execute:fg  obs="$51"
[ 63] other:shell  obs="New Terminal Output: "
[ 64] other:shell  obs="New Terminal Output: "
[ 65] other:shell  obs="New Terminal Output: "
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