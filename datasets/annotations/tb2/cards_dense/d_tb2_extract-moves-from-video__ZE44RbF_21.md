# Annotation card `d_tb2_extract-moves-from-video__ZE44RbF_21`

- corpus: `tb2`
- task id: `extract-moves-from-video`
- scaffold: `terminus-3-3`   model: `gemini-3.1-pro-preview@Google`
- trajectory length: 97 steps   final task reward: 0
- **window under judgement: steps 12–21 (w=10)**
- sampling note: dense position sample (stratified by scaffold and outcome)

## Task statement (all the information the agent was given)
```text
Download this video of someone playing zork. https://www.youtube.com/watch?v=ZCbvyPbhRfA. Then transcribe the entire contents of the text, and create a file /app/solution.txt that has all the moves they input, one per line, in the format 'n' or 'get bag' etc.
```

## Before the window (steps 0–11)
```text
[  0] no-tool  say="$31"
[  1] install:apt-get | install:pip3 | execute:yt-dlp(www.youtube.com/watch)  obs="$32"
[  2] other:shell  obs="$33"
[  3] install:pip3 | execute:yt-dlp(www.youtube.com/watch)  obs="$34"
[  4] other:shell  obs="$35"
[  5] execute:yt-dlp(best,www.youtube.com/watch)  obs="$36"
[  6] edit:cat(extract_frame.py,set())  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# cat << 'EOF' > extract_frame.py > import cv2 > import sys > > vid = cv2"
[  7] read:read(app/frame.png)  obs="File Read Result for '/app/frame.png': { "layout": "The text is laid out in a terminal-style interface with a status bar at the top showing "
[  8] edit:cat(extract_frames.py,frames/frame_)  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# cat << 'EOF' > extract_frames.py > import cv2 > import os > > os.makedi"
[  9] read:read(app/frames/frame_30500.png)  obs="File Read Result for '/app/frames/frame_30500.png': { "bottom_text": ">", "typing_command": false, "command": null, "full_line": ">" }"
[ 10] execute:$37  obs="$38"
[ 11] other:shell  obs="New Terminal Output: "
```

## WINDOW UNDER JUDGEMENT (steps 12–21)
```text
[ 12] other:shell  obs="New Terminal Output: "
[ 13] other:shell  obs="New Terminal Output: "
[ 14] other:shell  obs="New Terminal Output: "
[ 15] other:shell  obs="New Terminal Output: "
[ 16] other:shell  obs="New Terminal Output: "
[ 17] other:shell  obs="New Terminal Output: "
[ 18] other:shell  obs="New Terminal Output: "
[ 19] other:shell  obs="New Terminal Output: "
[ 20] other:shell  obs="New Terminal Output: "
[ 21] no-tool  say="$39"  obs="Previous response had parsing errors: ERROR: Invalid JSON: Invalid \escape: line 6 column 22 (char 1168) | Content preview: '{\n "analysis": "The `process_video.py` script is taking too long. It has been running for over 5 mi'... Please fix these issues and provide a proper JSON response."
```

## After the window (steps 22–35)
```text
[ 22] execute:c-c | execute:$3a  obs="$3b"
[ 23] other:shell  obs="New Terminal Output: "
[ 24] other:shell  obs="New Terminal Output: "
[ 25] no-tool  say="$3c"  obs="Previous response had parsing errors: ERROR: Invalid JSON: Invalid \escape: line 6 column 22 (char 546) | Content preview: '{\n "analysis": "
[ 26] execute:c-c | execute:$3d  obs="$3e"
[ 27] no-tool  say="$3f"  obs="Previous response had parsing errors: ERROR: Invalid JSON: Invalid \escape: line 6 column 22 (char 750) | Content preview: '{\n "analysis": "
[ 28] execute:c-c | edit:cat(check_diff.py,print())  obs="Current Terminal Screen: Time 4000ms: diff 0 Time 4250ms: diff 55 Time 4500ms: diff 0 Time 4750ms: diff 0 Time 5000ms: diff 0 Time 5250ms: d"
[ 29] execute:$40  obs="$41"
[ 30] other:shell  obs="New Terminal Output: "
[ 31] other:shell  obs="New Terminal Output: "
[ 32] other:shell  obs="New Terminal Output: "
[ 33] other:shell  obs="New Terminal Output: "
[ 34] execute:c-c | execute:$42  obs="$43"
[ 35] other:shell  obs="New Terminal Output: Found 140 key frames. Running OCR... Time 11667ms: n Time 12833ms: u Time 14000ms: ope "
```

## Final steps of the trajectory
```text
[ 91] execute: | read:head(app/transcript.txt)  obs="$50"
[ 92] execute:python3(test_solution.py,test::test_solution.py)  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# python3 test_solution.py python3: can't open file '/app/test_solution.py': [Errno 2] No suc"
[ 93] edit:cat(test_solution.py,app/transcript.txt)  obs="$51"
[ 94] edit:rm(check_diff.py,stitch_commands.py)  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# rm -rf extract_*.py process_video*.py check_diff.py stitch_commands.py make_transcript.py t"
[ 95] control:mark_task_complete  obs="$52"
[ 96] control:mark_task_complete  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# "
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