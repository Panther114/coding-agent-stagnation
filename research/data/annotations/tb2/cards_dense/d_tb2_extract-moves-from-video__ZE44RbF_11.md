# Annotation card `d_tb2_extract-moves-from-video__ZE44RbF_11`

- corpus: `tb2`
- task id: `extract-moves-from-video`
- scaffold: `terminus-3-3`   model: `gemini-3.1-pro-preview@Google`
- trajectory length: 97 steps   final task reward: 0
- **window under judgement: steps 2–11 (w=10)**
- sampling note: dense sample, stride-2 refinement

## Task statement (all the information the agent was given)
```text
Download this video of someone playing zork. https://www.youtube.com/watch?v=ZCbvyPbhRfA. Then transcribe the entire contents of the text, and create a file /app/solution.txt that has all the moves they input, one per line, in the format 'n' or 'get bag' etc.
```

## Before the window (steps 0–1)
```text
[  0] no-tool  say="$31"
[  1] install:apt-get | install:pip3 | execute:yt-dlp(www.youtube.com/watch)  obs="$32"
```

## WINDOW UNDER JUDGEMENT (steps 2–11)
```text
[  2] other:shell  obs="$33"
[  3] install:pip3 | execute:yt-dlp(www.youtube.com/watch)  obs="$34"
[  4] other:shell  obs="$35"
[  5] execute:yt-dlp(best,www.youtube.com/watch)  obs="$36"
[  6] edit:cat(extract_frame.py,set())  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# cat << 'EOF' > extract_frame.py > import cv2 > import sys > > vid = cv2.VideoCapture('zork.mp4') > vid.set(cv2.CAP_PROP_POS_MSEC, 30000) # 30 seconds in > ret, frame = vid.read() > if ret: > cv2.imwrite('frame.png', frame) > print("
[  7] read:read(app/frame.png)  obs="File Read Result for '/app/frame.png': { "layout": "The text is laid out in a terminal-style interface with a status bar at the top showing 'Treasure Room', 'Score: 95', and 'Moves: 41'. Below that, the game's output and user input alternate. The text is left-aligned.", "command_location": "Commands"
[  8] edit:cat(extract_frames.py,frames/frame_)  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# cat << 'EOF' > extract_frames.py > import cv2 > import os > > os.makedirs('frames', exist_ok=True) > vid = cv2.VideoCapture('zork.mp4') > for t in [30000, 30500, 31000, 31500, 32000, 32500, 33000]: > vid.set(cv2.CAP_PROP_POS_MSEC, "
[  9] read:read(app/frames/frame_30500.png)  obs="File Read Result for '/app/frames/frame_30500.png': { "bottom_text": ">", "typing_command": false, "command": null, "full_line": ">" }"
[ 10] execute:$37  obs="$38"
[ 11] other:shell  obs="New Terminal Output: "
```

## After the window (steps 12–25)
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
[ 21] no-tool  say="$39"  obs="Previous response had parsing errors: ERROR: Invalid JSON: Invalid \escape: line 6 column 22 (char 1168) | Content preview: '{\n "analysis":"
[ 22] execute:c-c | execute:$3a  obs="$3b"
[ 23] other:shell  obs="New Terminal Output: "
[ 24] other:shell  obs="New Terminal Output: "
[ 25] no-tool  say="$3c"  obs="Previous response had parsing errors: ERROR: Invalid JSON: Invalid \escape: line 6 column 22 (char 546) | Content preview: '{\n "analysis": "
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