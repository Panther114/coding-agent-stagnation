# Annotation card `d_tb2_extract-moves-from-video__ZE44RbF_45`

- corpus: `tb2`
- task id: `extract-moves-from-video`
- scaffold: `terminus-3-3`   model: `gemini-3.1-pro-preview@Google`
- trajectory length: 97 steps   final task reward: 0
- **window under judgement: steps 36–45 (w=10)**
- sampling note: dense sample, stride-2 refinement

## Task statement (all the information the agent was given)
```text
Download this video of someone playing zork. https://www.youtube.com/watch?v=ZCbvyPbhRfA. Then transcribe the entire contents of the text, and create a file /app/solution.txt that has all the moves they input, one per line, in the format 'n' or 'get bag' etc.
```

## Before the window (steps 22–35)
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

## WINDOW UNDER JUDGEMENT (steps 36–45)
```text
[ 36] other:shell  obs="New Terminal Output: Time 14000ms: ope Time 16800ms: open ca Time 17733ms: popen case Time 19133ms: dLlight lamp Time 21700ms: slay trol Time 22633ms: g "
[ 37] other:shell  obs="New Terminal Output: Time 22633ms: g Time 23100ms: Y Time 26367ms: e Time 28467ms: put all but lamp Time 29167ms: case Time 30567ms: temple Time 31733ms: a Time 32900ms: open solid "
[ 38] other:shell  obs="New Terminal Output: Time 32900ms: open solid Time 34767ms: pray Time 36867ms: put sali Time 37567ms: put solid Time 38733ms: open trap Time 40133ms: d Time 41767ms: push a Time 42933ms: get toeol Time 43633ms: push all Time 45033ms: set n "
[ 39] other:shell  obs="New Terminal Output: Time 45033ms: set n Time 45967ms: S Time 47367ms: get Time 48533ms: get Time 50867ms: S Time 52500ms: pump Time 52967ms: boa Time 55533ms: put all but lamp, pump "
[ 40] other:shell  obs="New Terminal Output: Time 55533ms: put all but lamp, pump Time 56000ms: boat Time 57167ms: buat Time 57633ms: def late boat Time 58800ms: echo Time 60900ms: E Time 61833ms: drpo boat Time 62533ms: pum Time 63233ms: baat "
[ 41] other:shell  obs="New Terminal Output: Time 63233ms: baat Time 63700ms: boar Time 64633ms: launch Time 66033ms: Launch Time 68600ms: get out Time 70000ms: ne Time 70700ms: shove Time 71867ms: Y Time 73033ms: y Time 73733ms: opeu re "
[ 42] other:shell  obs="New Terminal Output: Time 73733ms: opeu re Time 74433ms: dget al Time 75600ms: g Time 77933ms: put bar,emeral Time 78400ms: boa Time 79333ms: get sharp Time 80500ms: get sharp Time 81433ms: get Time 82600ms: S Time 84467ms: Dwave sharp "
[ 43] other:shell  obs="New Terminal Output: Time 84467ms: Dwave sharp Time 85167ms: get Time 85633ms: SW Time 86333ms: mW Time 86800ms: W Time 88667ms: apen sa "
[ 44] other:shell  obs="New Terminal Output: Time 88667ms: apen sa Time 89133ms: Yopen sack Time 91700ms: put sharp, pot, bu Time 94033ms: put sharp, pot, bug Time 94733ms: purn Time 95433ms: boat, Time 98467ms: boat Time 98933ms: yget fork, trunk, bar, cmeral Time 100100ms: put all Time 100567ms: put all Time 102900ms: pu"
[ 45] other:shell  obs="New Terminal Output: Time 102900ms: put all Time 104067ms: uU Time 105000ms: temple Time 105933ms: get Time 106633ms: S Time 107567ms: get Time 108267ms: sav Time 109433ms: S Time 111067ms: d Time 112233ms: drop pair "
```

## After the window (steps 46–59)
```text
[ 46] other:shell  obs="New Terminal Output: Time 112233ms: drop pair Time 114100ms: get Time 117133ms: n Time 118767ms: rub mirro "
[ 47] other:shell  obs="New Terminal Output: Time 122733ms: put terch,ser Time 123433ms: put torch,screw Time 126467ms: get Time 126933ms: get Time 130200ms: put he"
[ 48] other:shell  obs="New Terminal Output: Time 135800ms: a Time 139300ms: Sopen Lid Time 140233ms: put heap Time 140933ms: Lid Time 141633ms: close li Time 14350"
[ 49] other:shell  obs="Current Terminal Screen: Time 109433ms: S Time 111067ms: d Time 112233ms: drop pair Time 114100ms: get Time 117133ms: n Time 118767ms: rub m"
[ 50] other:shell  obs="New Terminal Output: Time 164267ms: case Time 165433ms: u Time 166367ms: kill ma Time 168000ms: Y Time 168467ms: Y Time 168933ms: Y Time 172"
[ 51] other:shell  obs="New Terminal Output: Time 174533ms: temple Time 175467ms: pray Time 177567ms: pray Time 178500ms: get Time 178967ms: get Time 181067ms: put "
[ 52] edit:python3(extract_commands_fast.py,raw_commands.txt)  obs="New Terminal Output: root@8650887b-eddf-428f-be36-76737c73a7e6:/app# python3 extract_commands_fast.py > raw_commands.txt "
[ 53] other:shell  obs="New Terminal Output: "
[ 54] other:shell  obs="New Terminal Output: "
[ 55] other:shell  obs="New Terminal Output: "
[ 56] other:shell  obs="New Terminal Output: "
[ 57] other:shell  obs="New Terminal Output: "
[ 58] other:shell  obs="New Terminal Output: "
[ 59] other:shell  obs="New Terminal Output: "
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