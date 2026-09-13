# Annotation card `d_tb2_extract-moves-from-video__vRcGj7U_59`

- corpus: `tb2`
- task id: `extract-moves-from-video`
- scaffold: `terminus-3-3`   model: `gemini-3.1-pro-preview@Google`
- trajectory length: 105 steps   final task reward: 0
- **window under judgement: steps 50–59 (w=10)**
- sampling note: dense position sample (stratified by scaffold and outcome)

## Task statement (all the information the agent was given)
```text
Download this video of someone playing zork. https://www.youtube.com/watch?v=ZCbvyPbhRfA. Then transcribe the entire contents of the text, and create a file /app/solution.txt that has all the moves they input, one per line, in the format 'n' or 'get bag' etc.
```

## Before the window (steps 36–49)
```text
[ 36] execute:$44  obs="$45"
[ 37] other:shell  obs="New Terminal Output: Found 112 scroll frames. Frame 25: ['>'] Frame 340: ['>'] "
[ 38] execute: | control:kill | execute:$46  obs="$47"
[ 39] execute: | control:kill | execute:$48  obs="$49"
[ 40] other:shell  obs="New Terminal Output: "
[ 41] other:shell  obs="New Terminal Output: "
[ 42] other:shell  obs="New Terminal Output: "
[ 43] execute: | read:cat(app/solution.txt) | execute:fg  obs="Previous response had warnings: WARNINGS: - Command 1 should end with newline when followed by another command. Otherwise the two commands w"
[ 44] other:shell  obs="New Terminal Output: "
[ 45] other:shell  obs="New Terminal Output: "
[ 46] other:shell  obs="New Terminal Output: "
[ 47] other:shell  obs="New Terminal Output: "
[ 48] execute: | search:grep | execute:fg  obs="$4a"
[ 49] execute: | search:grep | execute:fg  obs="$4b"
```

## WINDOW UNDER JUDGEMENT (steps 50–59)
```text
[ 50] other:shell  obs="New Terminal Output: "
[ 51] other:shell  obs="New Terminal Output: "
[ 52] other:shell  obs="New Terminal Output: "
[ 53] execute: | search:grep | execute:fg  obs="$4c"
[ 54] other:shell  obs="New Terminal Output: "
[ 55] other:shell  obs="New Terminal Output: "
[ 56] other:shell  obs="New Terminal Output: "
[ 57] execute: | control:kill | execute:$4d  obs="$4e"
[ 58] execute:$4f  obs="$50"
[ 59] other:shell  obs="New Terminal Output: "
```

## After the window (steps 60–73)
```text
[ 60] other:shell  obs="New Terminal Output: "
[ 61] other:shell  obs="New Terminal Output: "
[ 62] execute: | search:grep | execute:fg  obs="$51"
[ 63] other:shell  obs="New Terminal Output: "
[ 64] other:shell  obs="New Terminal Output: "
[ 65] other:shell  obs="New Terminal Output: "
[ 66] other:shell  obs="New Terminal Output: "
[ 67] other:shell  obs="New Terminal Output: "
[ 68] execute: | search:grep | execute:fg  obs="$52"
[ 69] other:shell  obs="New Terminal Output: "
[ 70] execute: | control:kill | execute:$53  obs="$54"
[ 71] other:shell  obs="New Terminal Output: Processed frame 5 (1/134) Processed frame 320 (2/134) Processed frame 350 (3/134) Processed frame 385 (4/134) "
[ 72] other:shell  obs="New Terminal Output: Processed frame 420 (5/134) Processed frame 455 (6/134) Processed frame 505 (7/134) "
[ 73] other:shell  obs="New Terminal Output: Processed frame 505 (7/134) Processed frame 535 (8/134) Processed frame 570 (9/134) Processed frame 600 (10/134) Proces"
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