# Annotation card (round 2, reduced context) `tb2_llm-inference-batching-scheduler__ubwAnFp_53`

- scaffold `openhands`, model `gpt-5-mini@openai`, trajectory length 72 steps, final reward 1
- **window under judgement: steps 44–53 (w=10)**

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

## Immediately before (steps 41–43)
```text
[ 41] execute:$52  say="$51"
[ 42] execute:$54  say="$53"  obs="$55"
[ 43] execute:$57  say="$56"
```

## WINDOW (steps 44–53)
```text
[ 44] execute:$59  say="$58"  obs="merged cost 440914629095.0 pad_ratio 0.07897402580749947 p95 2323725.7671999997 seq_timecost 266601766.3411999 written"
[ 45] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Running command: python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r="
[ 46] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Command `python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r=json.loa"  obs="python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r=json.loads(line) reqs[r['request_id']]=r plan=[] with ope"
[ 47] edit:python3(task_file/output_data/plan_b1.jsonl,task_file/output_data/plan_b2.jsonl)  say="Running command: python3 - << 'PY' import json from collections import Counter p1='task_file/output_data/plan_b1.jsonl' p2='task_file/output_data/plan_b2.jsonl' for p in [p1,p2]: cnt=0 shapes=Counter() batches=set() with"
[ 48] edit:python3(task_file/output_data/plan_b1.jsonl,task_file/output_data/plan_b2.jsonl)  say="Command `python3 - << 'PY' import json from collections import Counter p1='task_file/output_data/plan_b1.jsonl' p2='task_file/output_data/plan_b2.jsonl' for p in [p1,p2]: cnt=0 shapes=Counter() batches=set() with open(p)"  obs="task_file/output_data/plan_b1.jsonl records 800 unique shapes 8 batches 268 shapes counts [(128, 276), (64, 134), (704, 93), (384, 89), (512, 86), (1536, 68), (1472, 52), (2048, 2)] task_file/output_data/plan_b2.jsonl records 800 unique shapes 6 batches 132 sh"
[ 49] edit:python3(task_file/input_data/requests_bucket_,task_file/output_data/plan_b)  say="Running command: python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json cm=CostModel(64) for b in [1,2]: with open(f'task_file/input_data/requests_bucket_{b}.jsonl') as f: reqs={json.loads(line)"
[ 50] edit:python3(task_file/input_data/requests_bucket_,task_file/output_data/plan_b)  say="Command `python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json cm=CostModel(64) for b in [1,2]: with open(f'task_file/input_data/requests_bucket_{b}.jsonl') as f: reqs={json.loads(line)['reques"  obs="bucket 1 cost 440914629095.0 pad_ratio 0.07897402580749947 p95 2323725.7671999997 seq_timecost 266601766.3411999 bucket 2 cost 43672903863.0 pad_ratio 0.13695723059981932 p95 192365.8 seq_timecost 31484993.58440002"
[ 51] execute:$5b  say="$5a"
[ 52] execute:$5d  say="$5c"  obs="$5e"
[ 53] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Running command: python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r="
```

## Immediately after (steps 54–56)
```text
[ 54] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Command `python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open"  obs="python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests"
[ 55] execute:$60  say="$5f"
[ 56] execute:$62  say="$61"  obs="$63"
```

## Your label
```
label: PRODUCTIVE | STAGNANT | REGRESSION | DONE_REDUNDANT | BLOCKED_EXTERNAL | UNCERTAIN
confidence: high | medium | low
channels_advanced: E | I | V | none
justification: at most 25 words, cite step numbers
```