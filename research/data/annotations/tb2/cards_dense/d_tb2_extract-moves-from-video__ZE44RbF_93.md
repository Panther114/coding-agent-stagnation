# Annotation card `d_tb2_extract-moves-from-video__ZE44RbF_93`

- corpus: `tb2`
- task id: `extract-moves-from-video`
- scaffold: `terminus-3-3`   model: `gemini-3.1-pro-preview@Google`
- trajectory length: 97 steps   final task reward: 0
- **window under judgement: steps 84–93 (w=10)**
- sampling note: dense sample, stride-2 refinement

## Task statement (all the information the agent was given)
```text
Download this video of someone playing zork. https://www.youtube.com/watch?v=ZCbvyPbhRfA. Then transcribe the entire contents of the text, and create a file /app/solution.txt that has all the moves they input, one per line, in the format 'n' or 'get bag' etc.
```

## Before the window (steps 70–83)
```text
[ 70] execute:$45  obs="$46"
[ 71] execute: | execute:$47  obs="$48"
[ 72] other:shell  obs="New Terminal Output: Found 140 key frames. Cropping and stitching... Saved stitched_commands.png root@8650887b-eddf-428f-be36-76737c73a7e6:/"
[ 73] read:read(app/stitched_commands.png)  obs="$49"
[ 74] edit:cat(description.txt,www.youtube.com/watch)  obs="$4a"
[ 75] execute:$4b  obs="$4c"
[ 76] other:shell  obs="New Terminal Output: "
[ 77] other:shell  obs="New Terminal Output: "
[ 78] other:shell  obs="New Terminal Output: "
[ 79] other:shell  obs="New Terminal Output: "
[ 80] other:shell  obs="New Terminal Output: "
[ 81] other:shell  obs="New Terminal Output: "
[ 82] execute: | read:cat(raw_precise.txt)  obs="$4d"
[ 83] execute:$4e  obs="Current Terminal Screen: > cage > lower cage > ne > drop all > w > get all from case > open lid > put heap > lid > close lid > set switch > "
```

## WINDOW UNDER JUDGEMENT (steps 84–93)
```text
[ 84] edit:cat(make_transcript.py,app/transcript.txt) | edit:cat(test_solution.py,app/transcript.txt)  obs="$4f"
[ 85] other:shell  obs="New Terminal Output: "
[ 86] other:shell  obs="New Terminal Output: "
[ 87] other:shell  obs="New Terminal Output: "
[ 88] other:shell  obs="New Terminal Output: "
[ 89] other:shell  obs="New Terminal Output: "
[ 90] other:shell  obs="New Terminal Output: "
[ 91] execute: | read:head(app/transcript.txt)  obs="$50"
[ 92] execute:python3(test_solution.py,test::test_solution.py)  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# python3 test_solution.py python3: can't open file '/app/test_solution.py': [Errno 2] No such file or directory root@8650887b-eddf-428f-be36-76737c73a7e6:/app# "
[ 93] edit:cat(test_solution.py,app/transcript.txt)  obs="$51"
```

## After the window (steps 94–96)
```text
[ 94] edit:rm(check_diff.py,stitch_commands.py)  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# rm -rf extract_*.py process_video*.py check_diff.py stitch_commands.py "
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