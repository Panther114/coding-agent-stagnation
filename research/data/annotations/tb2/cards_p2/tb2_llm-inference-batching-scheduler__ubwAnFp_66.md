# Annotation card (round 2, reduced context) `tb2_llm-inference-batching-scheduler__ubwAnFp_66`

- scaffold `openhands`, model `gpt-5-mini@openai`, trajectory length 72 steps, final reward 1
- **window under judgement: steps 57–66 (w=10)**

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

## Immediately before (steps 54–56)
```text
[ 54] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Command `python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open"  obs="python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests"
[ 55] execute:$60  say="$5f"
[ 56] execute:$62  say="$61"  obs="$63"
```

## WINDOW (steps 57–66)
```text
[ 57] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Running command: python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r="
[ 58] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Command `python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r=json.loa"  obs="python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r=json.loads(line) reqs[r['request_id']]=r plan=[] with ope"
[ 59] edit:python3(task_file/input_data/requests_bucket_1.jsonl,task_file/input_data/requests_bucket_2.jsonl)  say="Running command: python3 - << 'PY' from task_file.scripts.cost_model import align import json c1=0 with open('task_file/input_data/requests_bucket_1.jsonl') as f: for line in f: r=json.loads(line) if align(r['prompt_len'"
[ 60] edit:python3(task_file/input_data/requests_bucket_1.jsonl,task_file/input_data/requests_bucket_2.jsonl)  say="Command `python3 - << 'PY' from task_file.scripts.cost_model import align import json c1=0 with open('task_file/input_data/requests_bucket_1.jsonl') as f: for line in f: r=json.loads(line) if align(r['prompt_len'],64)==2"  obs="2048 counts 17 0"
[ 61] execute:$65  say="$64"
[ 62] execute:$67  say="$66"  obs="$68"
[ 63] execute:$6a  say="$69"
[ 64] execute:$6c  say="$6b"  obs="$6d"
[ 65] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Running command: python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r="
[ 66] edit:python3(input_data/requests_bucket_,output_data/plan_b)  say="Command `python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r=json.loa"  obs="python3 - << 'PY' from task_file.scripts.cost_model import CostModel import json root='task_file' for b in [1,2]: reqs={} with open(f'{root}/input_data/requests_bucket_{b}.jsonl') as f: for line in f: r=json.loads(line) reqs[r['request_id']]=r plan=[] with ope"
```

## Immediately after (steps 67–69)
```text
[ 67] edit:python3(task_file/output_data/plan_b,task_file/input_data/requests_bucket_)  say="Running command: python3 - << 'PY' import json from collections import Counter from task_file.scripts.cost_model import CostModel cm=CostMod"
[ 68] edit:python3(task_file/output_data/plan_b,task_file/input_data/requests_bucket_)  say="Command `python3 - << 'PY' import json from collections import Counter from task_file.scripts.cost_model import CostModel cm=CostModel(64) f"  obs="Plan task_file/output_data/plan_b1.jsonl unique shapes 6 shapes [64, 128, 320, 576, 640, 2048] batches 250 metrics: cost 296577591117.0 pad_ratio 0.050817864363"
[ 69] execute:$6f  say="$6e"
```

## Your label
```
label: PRODUCTIVE | STAGNANT | REGRESSION | DONE_REDUNDANT | BLOCKED_EXTERNAL | UNCERTAIN
confidence: high | medium | low
channels_advanced: E | I | V | none
justification: at most 25 words, cite step numbers
```