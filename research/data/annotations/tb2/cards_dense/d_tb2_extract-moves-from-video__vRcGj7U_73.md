# Annotation card `d_tb2_extract-moves-from-video__vRcGj7U_73`

- corpus: `tb2`
- task id: `extract-moves-from-video`
- scaffold: `terminus-3-3`   model: `gemini-3.1-pro-preview@Google`
- trajectory length: 105 steps   final task reward: 0
- **window under judgement: steps 64–73 (w=10)**
- sampling note: dense sample, stride-2 refinement

## Task statement (all the information the agent was given)
```text
Download this video of someone playing zork. https://www.youtube.com/watch?v=ZCbvyPbhRfA. Then transcribe the entire contents of the text, and create a file /app/solution.txt that has all the moves they input, one per line, in the format 'n' or 'get bag' etc.
```

## Before the window (steps 50–63)
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
[ 60] other:shell  obs="New Terminal Output: "
[ 61] other:shell  obs="New Terminal Output: "
[ 62] execute: | search:grep | execute:fg  obs="$51"
[ 63] other:shell  obs="New Terminal Output: "
```

## WINDOW UNDER JUDGEMENT (steps 64–73)
```text
[ 64] other:shell  obs="New Terminal Output: "
[ 65] other:shell  obs="New Terminal Output: "
[ 66] other:shell  obs="New Terminal Output: "
[ 67] other:shell  obs="New Terminal Output: "
[ 68] execute: | search:grep | execute:fg  obs="$52"
[ 69] other:shell  obs="New Terminal Output: "
[ 70] execute: | control:kill | execute:$53  obs="$54"
[ 71] other:shell  obs="New Terminal Output: Processed frame 5 (1/134) Processed frame 320 (2/134) Processed frame 350 (3/134) Processed frame 385 (4/134) "
[ 72] other:shell  obs="New Terminal Output: Processed frame 420 (5/134) Processed frame 455 (6/134) Processed frame 505 (7/134) "
[ 73] other:shell  obs="New Terminal Output: Processed frame 505 (7/134) Processed frame 535 (8/134) Processed frame 570 (9/134) Processed frame 600 (10/134) Processed frame 650 (11/134) "
```

## After the window (steps 74–87)
```text
[ 74] other:shell  obs="New Terminal Output: Processed frame 650 (11/134) Processed frame 680 (12/134) Processed frame 710 (13/134) Processed frame 745 (14/134) "
[ 75] other:shell  obs="New Terminal Output: Processed frame 790 (15/134) Processed frame 855 (16/134) Processed frame 885 (17/134) Processed frame 915 (18/134) "
[ 76] other:shell  obs="New Terminal Output: Processed frame 915 (18/134) Processed frame 955 (19/134) Processed frame 985 (20/134) Processed frame 1015 (21/134) "
[ 77] other:shell  obs="New Terminal Output: Processed frame 1015 (21/134) Processed frame 1045 (22/134) Processed frame 1075 (23/134) Processed frame 1105 (24/134)"
[ 78] other:shell  obs="New Terminal Output: Processed frame 1190 (26/134) Processed frame 1220 (27/134) Processed frame 1255 (28/134) Processed frame 1290 (29/134)"
[ 79] other:shell  obs="New Terminal Output: Processed frame 1290 (29/134) Processed frame 1325 (30/134) Processed frame 1355 (31/134) Processed frame 1385 (32/134)"
[ 80] other:shell  obs="New Terminal Output: Processed frame 1385 (32/134) Processed frame 1420 (33/134) Processed frame 1450 (34/134) Processed frame 1480 (35/134)"
[ 81] execute: | control:kill | execute:$55  obs="$56"
[ 82] read:sed(s/import,fast_sequence_ocr.py)  obs="New Terminal Output: root@8adacdf9-45a9-4334-9496-c4410a45d812:/app# sed -i 's/import pytesseract/import pytesseract\nimport numpy as np/g' "
[ 83] other:shell  obs="$57"
[ 84] other:shell  obs="New Terminal Output: Processed frame 3690 (90/134) Processed frame 3720 (91/134) Processed frame 3750 (92/134) Processed frame 3780 (93/134)"
[ 85] other:shell  obs="New Terminal Output: Processed frame 4250 (107/134) Processed frame 4300 (108/134) Processed frame 4330 (109/134) Processed frame 4385 (110/"
[ 86] other:shell  obs="New Terminal Output: Processed frame 5055 (125/134) Processed frame 5185 (126/134) Processed frame 5230 (127/134) Processed frame 5260 (128/"
[ 87] read:cat(app/solution.txt)  obs="Current Terminal Screen: se d get u n put cage lower cage d se d drop a get put he Lid se set switch e u e get s get h s put al get egg wW g"
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