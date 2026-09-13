# Annotation card (round 2, reduced context) `tb2_llm-inference-batching-scheduler__ubwAnFp_19`

- scaffold `openhands`, model `gpt-5-mini@openai`, trajectory length 72 steps, final reward 1
- **window under judgement: steps 10–19 (w=10)**

## Task statement
```text
In this task you will implement an **LLM inference batching scheduler (shape‑aware)**
for a static graph LLM inference system.  
**Background **
When running large language models on hardware
accelerators (such as TPUs, RDUs, or bespoke inference chips) the compiled
execution graph has to operate on fixed‑sized tensors.  Requests arrive
with arbitrary prompt lengths and generation lengths, but at runtime
everything must be rounded up to a multiple of a common granularity.  A
naïve strategy of batching each request independently wastes compute,
increases the number of cold compilations and leads to poor end‑to‑end
latency.

**Goal**
Your goal is to read a set of incoming requests from ``/app/task_file/input_data/requests_bucket_1.jsonl``
``/app/task_file/input_data/requests_bucket_2.jsonl`` and produce a plan in 
``/app/task_file/output_data/plan_b1.jsonl`` 
``/app/task_file/output_data/plan_b2.jsonl`` 
that assigns every request to a batch
along with a concrete tensor shape (defined by ``shape.seq_align``, ``shape.heads_align``, ``shape.hidden_align``).  
Each entry in ``/app/task_file/input_data/requests_bucket_1.jsonl`` and ``/app/task_file/input_data/requests_bucket_2.jsonl`` is
a JSON object containing a unique ``request_id``, a ``prompt_len`` and
``gen_len``:

  * ``request_id``: A unique string identifier for each inference request (e.g., "r-000010")
  * ``prompt_len``: The length of the input prompt in tokens (integer). 
  * ``gen_len``: The number of tokens to generate for this request (integer). 

You must pack these into batches so that:

  * All input requests are included exactly once (no missing/duplicate request_ids)
  * Each batch uses shape (seq_align, heads_align=32, hidden_align=4096) where seq_align >= ceil(prompt_len/64)*64. I.e., seq_align is a multiple of 64.
  * Max 8 unique shapes (seq_align, heads_align, hidden_align) across both buckets (MAX_SHAPES=8)
  * One record per request_id, identical shapes within each batch_id

To aid development w
```

## Immediately before (steps 7–9)
```text
[  7] edit:edit  say="Reading file: /app/task_file/input_data/requests_bucket_1.jsonl"
[  8] edit:edit  say="I read the file /app/task_file/input_data/requests_bucket_1.jsonl."  obs="$35"
[  9] edit:edit  say="Reading file: /app/task_file/scripts/cost_model.py"
```

## WINDOW (steps 10–19)
```text
[ 10] edit:edit  say="I read the file /app/task_file/scripts/cost_model.py."  obs="$36"
[ 11] edit:edit  say="Reading file: /app/task_file/scripts/baseline_packer.py"
[ 12] edit:edit  say="I read the file /app/task_file/scripts/baseline_packer.py."  obs="$37"
[ 13] read:wc(app/task_file/input_data/requests_bucket_1.jsonl,app/task_file/input_data/requests_bucket_2.jsonl)  say="Running command: wc -l /app/task_file/input_data/requests_bucket_1.jsonl && wc -l /app/task_file/input_data/requests_bucket_2.jsonl"
[ 14] read:wc(app/task_file/input_data/requests_bucket_1.jsonl,app/task_file/input_data/requests_bucket_2.jsonl)  say="Command `wc -l /app/task_file/input_data/requests_bucket_1.jsonl && wc -l /app/task_file/input_data/requests_bucket_2.jsonl` executed with exit code 0."  obs="800 /app/task_file/input_data/requests_bucket_1.jsonl 800 /app/task_file/input_data/requests_bucket_2.jsonl"
[ 15] execute:python3(app/task_file/scripts/baseline_packer.py,app/task_file/output_data)  say="Running command: python3 /app/task_file/scripts/baseline_packer.py && echo 'baseline written' && ls -l /app/task_file/output_data"
[ 16] execute:python3(app/task_file/scripts/baseline_packer.py,app/task_file/output_data)  say="Command `python3 /app/task_file/scripts/baseline_packer.py && echo 'baseline written' && ls -l /app/task_file/output_data` executed with exit code 0."  obs="baseline written total 256 -rw-r--r-- 1 root root 128922 Nov 2 08:27 plan_b1.jsonl -rw-r--r-- 1 root root 130248 Nov 2 08:27 plan_b2.jsonl"
[ 17] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Running command: python3 - << 'PY' from task_file.scripts.cost_model import CostModel, CostConsts import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for l"
[ 18] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Command `python3 - << 'PY' from task_file.scripts.cost_model import CostModel, CostConsts import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f"  obs="python3 - << 'PY' from task_file.scripts.cost_model import CostModel, CostConsts import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r=json.loads(line) reqs[r['request_id']]=r plan"
[ 19] edit:python3(app/task_file/input_data/requests_bucket_1.jsonl,open())  say="Running command: python3 - << 'PY' import json from collections import Counter, defaultdict from task_file.scripts.cost_model import align paths=['/app/task_file/input_data/requests_bucket_1.jsonl','/app/task_file/input_"
```

## Immediately after (steps 20–22)
```text
[ 20] edit:python3(app/task_file/input_data/requests_bucket_1.jsonl,open())  say="Command `python3 - << 'PY' import json from collections import Counter, defaultdict from task_file.scripts.cost_model import align paths=['/"  obs="unique seq aligns total 27 most common aligned seqs [(128, 531), (64, 286), (320, 141), (192, 121), (256, 82), (576, 75), (512, 70), (384, 64), (640, 57), (448,"
[ 21] edit:python3(app/task_file/input_data/requests_bucket_1.jsonl,open())  say="Running command: python3 - << 'PY' import json from collections import Counter import math paths=['/app/task_file/input_data/requests_bucket"
[ 22] edit:python3(app/task_file/input_data/requests_bucket_1.jsonl,open())  say="Command `python3 - << 'PY' import json from collections import Counter import math paths=['/app/task_file/input_data/requests_bucket_1.jsonl"  obs="total reqs 1600 bins [('1-16', 365), ('17-32', 326), ('33-64', 438), ('65-128', 68), ('129-256', 296), ('257-512', 22), ('513-1024', 82), ('1025-2048', 3)] quan"
```

## Your label
```
label: PRODUCTIVE | STAGNANT | REGRESSION | DONE_REDUNDANT | BLOCKED_EXTERNAL | UNCERTAIN
confidence: high | medium | low
channels_advanced: E | I | V | none
justification: at most 25 words, cite step numbers
```