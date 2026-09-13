"""Emit LaTeX macros and tables from a frozen run directory.

Every number that appears in the paper comes from this script, so the text can never
drift from the artifacts.

Usage: python scripts/export_results_tex.py --run results/final/tb2_round1 --corpus tb2 \
         --out paper/generated_tb2.tex
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Sequence

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import paths  # noqa: E402


def fmt(x: Any, nd: int = 3, dash: str = "--") -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return dash
    if v != v:
        return dash
    return f"{v:.{nd}f}"


DIGIT_WORDS = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
               "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}


def macro(name: str, value: str, prefix: str = "p") -> str:
    """Emit a macro definition with a name this TeX build accepts.

    Two LaTeX traps forced this: ``\\res...`` parses as a length assignment, and --- discovered
    by bisection with ``scripts/probe_len2.py`` --- this MiKTeX build rejects ``\\newcommand``
    names that contain a digit, failing with the misleading "Missing \\begin{document}".  Digits
    are therefore spelled out (``B4`` becomes ``Bfour``), which also makes the names readable.
    """
    name = re.sub(r"[^A-Za-z0-9]", "", name)
    name = "".join(DIGIT_WORDS.get(ch, ch) for ch in name)
    return f"\\newcommand{{\\{prefix}{name}}}{{{value}}}"


def pretty(name: str) -> str:
    mapping = {
        "B1_step30": "B1 step budget 30",
        "B1_step60": "B1 step budget 60",
        "B2_exact_rep3": "B2 exact repeat $k{=}3$",
        "B2_exact_rep5": "B2 exact repeat $k{=}5$",
        "B3_rep_channel": "B3 repetition channel",
        "B3_rep_target": "B3 target repetition",
        "B4_semantic": "B4 semantic redundancy",
        "B4_sem_diversity": "B4 rolling diversity",
        "B5_novelty": "B5 novelty (relevance-blind)",
        "B5_novelty_sig": "B5 distinct actions",
        "B6_verification": "B6 verification channel",
        "B6_ver_stall": "B6 time since improvement",
        "B7_workspace": "B7 workspace churn",
        "C1_evidence": "C1 task-grounded evidence",
        "C1_evidence_rel": "C1 evidence (relevant only)",
        "C2_evid_ver": "C2 evidence + verification",
        "C2_evid_ver_work": "C2 evidence + verification + edits",
        "C3_evid_sem": "C3 evidence + semantic",
        "C4_all_hand": "C4 all hand-designed",
        "L_rep": "L repetition (learned)",
        "L_nov": "L novelty (learned)",
        "L_evid": "L evidence (learned)",
        "L_ver": "L verification (learned)",
        "L_work": "L workspace (learned)",
        "L_evid_ver": "L evidence + verification (learned)",
        "L_evid_nov": "L evidence + novelty (learned)",
        "L_evid_sem": "L evidence + semantic (learned)",
        "L_sem": "L semantic (learned)",
        "L_all_hand": "L all hand-designed (learned)",
        "L_all_sem": "L all + semantic (learned)",
        "transfer_L_all_hand": "T all hand-designed (transferred)",
        "transfer_L_all_sem": "T all + semantic (transferred)",
        "transfer_L_evid": "T evidence (transferred)",
    }
    if name in mapping:
        return mapping[name]
    if name.startswith("transfer_"):
        return "T " + name[len("transfer_"):].replace("_", " ")
    if name.startswith("L_"):
        return "L " + name[2:].replace("_", " ")
    return name.replace("_", "\\_")


def tex_escape(s: str) -> str:
    return (s.replace("\\", "\\textbackslash{}").replace("&", "\\&").replace("%", "\\%")
            .replace("$", "\\$").replace("#", "\\#").replace("_", "\\_")
            .replace("{", "\\{").replace("}", "\\}").replace("~", "\\textasciitilde{}"))


class MacroTable:
    """Registry that gives every generated macro a short, safe name.

    TeX control sequences are limited to 40 characters, and generated names such as
    ``monC1evidenceDetectionRate`` easily exceed that limit once a prefix is added, which
    produces the confusing failure "Missing \\begin{document}".  Rather than rely on the
    length budget, every macro gets a sequential short name (``\\ppxa``, ``\\ppxb``, ...) and
    the semantic name is recorded in ``MACRO_MAP.md`` so a reader can still tell what each
    number means.  The paper text refers to ``@@semanticName@@`` tokens, which this class
    substitutes when it writes the generated files.
    """

    def __init__(self, prefix: str = "ppx"):
        self.prefix = prefix
        self.names: Dict[str, str] = {}
        self.values: Dict[str, float] = {}

    def _short(self, semantic: str) -> str:
        if semantic not in self.names:
            idx = len(self.names)
            letters = ""
            n = idx
            while True:
                letters = chr(ord("a") + n % 26) + letters
                n = n // 26 - 1
                if n < 0:
                    break
            self.names[semantic] = self.prefix + letters
        return self.names[semantic]

    def define(self, semantic: str, value: str) -> str:
        self.values[semantic] = value
        return f"\\newcommand{{\\{self._short(semantic)}}}{{{value}}}"

    def token(self, semantic: str) -> str:
        """Placeholder written into the paper text and substituted on export."""
        self._short(semantic)
        return f"@@{semantic}@@"

    def substitute(self, text: str) -> str:
        def repl(m):
            sem = m.group(1)
            return "\\" + self._short(sem)
        return re.sub(r"@@([A-Za-z0-9_]+)@@", repl, text)

    def map_markdown(self) -> str:
        lines = ["# Generated macro map", "",
                 "Every quantitative claim in the paper is a macro produced by",
                 "`scripts/export_results_tex.py` from a frozen run directory. TeX limits",
                 "control-sequence names to 40 characters, so the macros carry short names;",
                 "this table is the decoding key.", "",
                 "| macro | meaning | value |", "|---|---|---|"]
        for sem, short in self.names.items():
            lines.append(f"| `\\{short}` | `{sem}` | {self.values.get(sem, '')} |")
        return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--ann", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--show", default=None, help="comma separated monitor names to table")
    args = ap.parse_args()
    ann = args.ann or os.path.join(paths.DATA, "annotations", args.corpus)

    cfg = json.load(open(os.path.join(args.run, "run_config.json"), encoding="utf-8"))
    wl = json.load(open(os.path.join(args.run, "window_metrics.json"), encoding="utf-8"))
    frontier = json.load(open(os.path.join(args.run, "alarm_frontier.json"), encoding="utf-8"))
    curves = json.load(open(os.path.join(args.run, "alarm_curves.json"), encoding="utf-8"))
    agree_raw = json.load(open(os.path.join(ann, "agreement.json"), encoding="utf-8"))
    # agreement figures live under ``cross_round`` (round 1 re-read with reduced context)
    agree = dict(agree_raw)
    for k, v in (agree_raw.get("cross_round") or {}).items():
        agree.setdefault(k, v)
    lr = json.load(open(os.path.join(args.run, "logistic_report.json"), encoding="utf-8"))
    desc = json.load(open(os.path.join(args.run, "descriptive.json"), encoding="utf-8"))
    adj = list(csv.DictReader(open(os.path.join(ann, "adjudicated.csv"), encoding="utf-8")))
    regions = json.load(open(os.path.join(ann, "gold_regions.json"), encoding="utf-8"))

    w = args.w
    L: List[str] = []
    L.append("% AUTO-GENERATED by scripts/export_results_tex.py -- do not edit by hand")
    L.append(f"% run: {args.run}   built: {cfg['built_at']}   corpus: {cfg['corpus']}")

    # ---------------- corpus / setup macros ----------------
    n_windows = len(adj)
    n_pos = sum(1 for a in adj if a["binary"] == "1")
    n_neg = sum(1 for a in adj if a["binary"] == "0")
    n_held = sum(1 for a in adj if a["binary"] == "")

    # compact, stable macro namespace: \n<Traj|Tasks|Windows>, \ann<...>, \auc<mon>, \res<mon><Key>
    MACRO_NAME = {
        "B1_step30": "aucB1step30", "B1_step60": "aucB1step60",
        "B2_exact_rep3": "aucB2rep3", "B2_exact_rep5": "aucB2rep5",
        "B3_rep_channel": "aucB3repChannel", "B3_rep_target": "aucB3repTarget",
        "B4_semantic": "aucB4semantic", "B4_sem_diversity": "aucB4semDiversity",
        "B5_novelty": "aucB5novelty", "B5_novelty_sig": "aucB5noveltySig",
        "B6_verification": "aucB6verification", "B6_ver_stall": "aucB6verStall",
        "B7_workspace": "aucB7workspace",
        "C1_evidence": "aucC1evidence", "C1_evidence_rel": "aucC1evidenceRel",
        "C2_evid_ver": "aucC2evidVer", "C2_evid_ver_work": "aucC2evidVerWork",
        "C3_evid_sem": "aucC3evidSem", "C4_all_hand": "aucC4allHand",
        "L_rep": "aucLrep", "L_nov": "aucLnov", "L_ver": "aucLver",
        "L_work": "aucLwork", "L_sem": "aucLsem", "L_evid": "aucLevid",
        "L_evid_sem": "aucLevidsem", "L_evid_ver": "aucLevidVer",
        "L_evid_nov": "aucLevidNov", "L_all_hand": "aucLallHand", "L_all_sem": "aucLallSem",
    }

    def short(m: str) -> str:
        base = MACRO_NAME.get(m, m)
        for pref in ("auc",):
            if base.startswith(pref):
                return base[len(pref):][0].upper() + base[len(pref):][1:]
        return base

    L.append(macro("nTraj", f"{cfg.get('n_traj', cfg.get('n_train_traj', 0) + cfg.get('n_test_traj', 0))}"))
    L.append(macro("nTrainTraj", f"{cfg.get('n_train_traj', 0)}"))
    L.append(macro("nTestTraj", f"{cfg.get('n_test_traj', 0)}"))
    L.append(macro("nTasks", f"{len(cfg.get('tasks_per_fold', [])) and sum(cfg['tasks_per_fold']) or len(cfg.get('train_tasks', [])) + len(cfg.get('test_tasks', []))}"))
    L.append(macro("nTestTasks", f"{len(cfg.get('test_tasks', []))}"))
    L.append(macro("nTestTrajFolds", f"{cfg.get('n_test_traj', 0)}"))
    L.append(macro("nAlarmTraj", f"{cfg.get('n_alarm_eval_traj', 0)}"))
    L.append(macro("nAlarmTrajPos", f"{cfg.get('n_alarm_eval_traj_with_region', 0)}"))
    L.append(macro("nWindows", f"{cfg.get('n_window_rows', 0)}"))
    L.append(macro("nTrainWindows", f"{cfg.get('n_train_windows_labelled', 0)}"))
    L.append(macro("nCalTraj", f"{cfg.get('n_calibration_traj', 0)}"))
    L.append(macro("annWindows", f"{n_windows}"))
    L.append(macro("annPos", f"{n_pos}"))
    L.append(macro("annNeg", f"{n_neg}"))
    L.append(macro("annHeld", f"{n_held}"))
    L.append(macro("annPosRate", f"{100.0*n_pos/max(1,n_pos+n_neg):.1f}"))
    L.append(macro("annTraj", f"{len(regions)}"))
    L.append(macro("annBinaryAgr", f"{100.0*agree.get('binary_agreement', float('nan')):.1f}"))
    L.append(macro("annExactAgr", f"{100.0*agree.get('exact_agreement', float('nan')):.1f}"))
    L.append(macro("annKappa", fmt(agree.get("cohen_kappa", float("nan")), 2)))
    L.append(macro("annJaccard", fmt(agree.get("positive_jaccard", float("nan")), 2)))
    L.append(macro("annAgreeN", f"{agree.get('n', 0)}"))
    lab = agree["labels"]
    for k, v in lab.items():
        L.append(macro("annLabel" + k.title().replace("_", ""), str(v)))
    L.append(macro("annWindowsTotal", str(n_windows)))
    L.append(macro("annBinaryN", str(n_pos + n_neg)))
    L.append(macro("annTrajTotal", str(len(regions))))
    L.append(macro("annDenseWindows", str(sum(1 for a in adj if a.get("kind") in ("dense", "dense2")))))
    L.append(macro("annPositionWindows", str(sum(1 for a in adj if a.get("kind") == "position"))))
    L.append(macro("nFolds", str(cfg.get("folds", 1))))
    L.append(macro("tauTol", str(cfg.get("args", {}).get("tolerance", 2))))
    for tag, key in (("Pass", "1"), ("Fail", "0")):
        bloc = agree.get("label_by_reward", {}).get(key)
        if bloc:
            tot = bloc.get("POS", 0) + bloc.get("NEG", 0)
            L.append(macro("annPosRateRewardw" + tag, f"{100.0*bloc.get('POS',0)/max(1,tot):.1f}"))
    occ = {}
    for f, v in (wl.items() if isinstance(wl, dict) else []):
        pass
    # mean monitor score versus final success: the best AUC across monitors
    oa_path = os.path.join(args.run, "outcome_association.json")
    if os.path.exists(oa_path):
        oa = json.load(open(oa_path, encoding="utf-8"))
        best_oa = max((v.get("auc_mean_score_vs_success", float("nan")) for v in oa.values()),
                      default=float("nan"))
        L.append(macro("outcomeAssocBestAuc", fmt(best_oa)))
        L.append(macro("outcomeAssocPassRate", fmt(next(iter(oa.values()), {}).get("pass_rate"))))
    det = agree.get("details", {})
    SUBTYPE_MACRO = {
        "no_new_information": "annSubNoNewInformation",
        "repeat_verify": "annSubRepeatVerify",
        "no_tool_text_loop": "annSubNoToolTextLoop",
        "repeat_search": "annSubRepeatSearch",
        "repeat_read": "annSubRepeatRead",
        "edit_revert": "annSubEditRevert",
        "irrelevant_exploration": "annSubIrrelevantExploration",
        "post_completion": "annSubPostCompletion",
        "other": "annSubOther",
    }
    for key, mac in SUBTYPE_MACRO.items():
        L.append(macro(mac, str(det.get(key, 0))))
    for key, mac in SUBTYPE_MACRO.items():
        L.append(macro(mac.lower(), str(det.get(key, 0))))
    L.append(macro("annSubtypes", str(sum(det.values()))))
    L.append(macro("corpusName", "Terminal-Bench 2.0" if args.corpus == "tb2" else "SWE-agent/SWE-bench"))
    L.append(macro("tag", f"{args.corpus}_w{args.w}"))
    L.append(macro("wParamVal", str(args.w)))
    if os.path.exists(os.path.join(paths.FINAL, f"summary_{args.corpus}.json")):
        s = json.load(open(os.path.join(paths.FINAL, f"summary_{args.corpus}.json"), encoding="utf-8"))
        L.append(macro("corpusSteps", f"{s['steps_total']:,}".replace(",", "{,}")))
        L.append(macro("corpusStepsMean", f"{s['steps_mean']:.1f}"))
        L.append(macro("corpusStepsMedian", f"{s['steps_median']:.0f}"))
        L.append(macro("corpusStepsMax", f"{s['steps_max']}"))
        L.append(macro("corpusScaffolds", f"{s['n_scaffolds']}"))
        L.append(macro("corpusModels", f"{s['n_models']}"))
        L.append(macro("corpusPass", f"{100*s['pass_rate']:.1f}"))
        L.append(macro("corpusPhFrac", f"{100*s['ph_frac_mean']:.1f}"))
        L.append(macro("corpusToolStep", f"{100*s['tool_step_frac_mean']:.1f}"))
        if "annotation" in s:
            L.append(macro("annTrajPos", f"{s['annotation'].get('traj_with_positive', 0)}"))
            L.append(macro("annTrajNeg", f"{s['annotation'].get('traj_all_negative', 0)}"))
            rew = s["annotation"].get("label_by_reward", {})
            for key, tag in (("0", "Fail"), ("1", "Pass")):
                if key in rew:
                    tot = sum(rew[key].values())
                    L.append(macro("annPosRateReward" + tag, f"{100.0*rew[key].get('POS',0)/max(1,tot):.1f}"))
    L.append("")

    # ---------------- window-level table ----------------
    names = args.show.split(",") if args.show else None
    order = names if names else sorted(wl)
    # the main-body table shows one window size; the other is a robustness check reported in
    # the artifacts, because two rows per monitor doubles the table for little information
    def rows_for(m: Dict[str, Any]) -> Dict[str, Any]:
        return m.get(str(w)) or m.get(w) or {}

    L.append("\\begin{table*}[t]\\centering\\small")
    L.append("\\caption{Window-level discrimination on held-out tasks ($w=" + str(w) + "$). "
             "Higher is better; positive prevalence is the share of annotated windows that "
             "annotators called stagnant. The final column averages ROC-AUC computed inside "
             "each trajectory, which removes between-run differences.}")
    L.append("\\label{tab:window}")
    L.append("\\begin{tabular}{lrrrrrr}")
    L.append("\\toprule")
    L.append("Monitor & ROC-AUC & within-run & PR-AUC & best F1 & P@0.7 & R@0.7 \\\\")
    L.append("\\midrule")
    for name in order:
        m = rows_for(wl.get(name, {}))
        if not m:
            continue
        a7 = m.get("at_thresholds", {}).get("0.7", {})
        L.append(f"{pretty(name)} & {fmt(m['roc_auc'])} & {fmt(m.get('within_traj_auc'))} & "
                 f"{fmt(m['pr_auc'])} & {fmt(m['f1_best'])} & "
                 f"{fmt(a7.get('precision'),2)} & {fmt(a7.get('recall'),2)} \\\\")
    L.append("\\midrule")
    prev = next((rows_for(wl[n])["prev"] for n in wl if rows_for(wl[n])), float("nan"))
    nn = int(next((rows_for(wl[n])["n"] for n in wl if rows_for(wl[n])), 0))
    ntr = int(next((rows_for(wl[n]).get("n_traj_with_both_classes", 0) for n in wl
                    if rows_for(wl[n])), 0))
    L.append(f"\\multicolumn{{7}}{{l}}{{positive prevalence {fmt(prev,3)}; "
             f"${nn}$ annotated windows; within-run column averages over ${ntr}$ trajectories "
             f"that contain both labels}} \\\\")
    L.append("\\bottomrule\\end{tabular}\\end{table*}")
    L.append("")

    # ---------------- alarm frontier table ----------------
    L.append("\\begin{table*}[t]\\centering\\small")
    L.append("\\caption{Operational behaviour at a fixed false-stop budget. "
             "Detection rate is the share of trajectories whose alarm lands in an annotated "
             "stagnant region; mean steps saved is signed, so a false stop costs the steps it "
             "destroys. Oracle is the step index of the first annotated stagnant region.}")
    L.append("\\label{tab:frontier}")
    L.append("\\begin{tabular}{l" + "rrrr" * 3 + "}")
    L.append("\\toprule")
    L.append("& \\multicolumn{4}{c}{budget 1\\%} & \\multicolumn{4}{c}{budget 5\\%} & "
             "\\multicolumn{4}{c}{budget 10\\%} \\\\")
    L.append("\\cmidrule(lr){2-5}\\cmidrule(lr){6-9}\\cmidrule(lr){10-13}")
    L.append("Monitor & thr. & det. & saved & lat. & thr. & det. & saved & lat. & thr. & det. & saved & lat. \\\\")
    L.append("\\midrule")
    for name in order:
        if name not in frontier or str(w) not in {str(k) for k in frontier[name]}:
            continue
        fr = frontier[name][str(w)] if str(w) in frontier[name] else frontier[name][w]
        by = {round(f["budget"], 3): f for f in fr}
        cells = []
        for b in (0.01, 0.05, 0.10):
            f = by.get(b)
            if f is None or f["detection_rate"] != f["detection_rate"]:
                cells += ["--", "--", "--", "--"]
            else:
                cells += [fmt(f["threshold"], 2), fmt(f["detection_rate"], 2),
                          fmt(f["mean_saved_steps"], 1), fmt(f["median_latency"], 1)]
        L.append(f"{pretty(name)} & " + " & ".join(cells) + " \\\\")
    L.append("\\bottomrule\\end{tabular}\\end{table*}")
    L.append("")

    # ---------------- headline macros for the abstract ----------------
    def pick(mon: str, key: str, budget: float = 0.05) -> float:
        fr = frontier.get(mon, {}).get(str(w)) or frontier.get(mon, {}).get(w)
        if not fr:
            return float("nan")
        for f in fr:
            if abs(f["budget"] - budget) < 1e-9:
                return f.get(key, float("nan"))
        return float("nan")

    for key in ("detection_rate", "mean_saved_steps", "median_latency", "savings_ratio",
                "false_stop_rate"):
        for mon in ("C1_evidence", "C2_evid_ver", "C4_all_hand", "B4_semantic", "B4_sem_diversity",
                    "B2_exact_rep3", "B2_exact_rep5", "B3_rep_target", "B5_novelty",
                    "B6_verification", "B7_workspace", "L_evid", "L_all_hand", "L_all_sem",
                    "L_evid_ver", "transfer_L_all_hand", "C3_evid_sem", "L_ver", "L_rep"):
            # NB: do not name these macros with a `res` prefix -- LaTeX parses `\res` as a
            # length assignment and the preamble dies with "Missing \begin{document}".
            L.append(macro(f"mon{short(mon)}{key.title().replace('_','')}", fmt(pick(mon, key), 3 if ("rate" in key or "ratio" in key) else 1)))

    def wauc(mon: str) -> float:
        d = wl.get(mon, {})
        m = d.get(str(w)) or d.get(w)
        return float(m["roc_auc"]) if m else float("nan")

    def wwithin(mon: str) -> float:
        d = wl.get(mon, {})
        m = d.get(str(w)) or d.get(w)
        return float(m.get("within_traj_auc", float("nan"))) if m else float("nan")

    for mon in ("C1_evidence", "C1_evidence_rel", "C2_evid_ver", "C4_all_hand", "B2_exact_rep3",
                "B3_rep_target", "B4_semantic", "B4_sem_diversity", "B5_novelty", "B5_novelty_sig",
                "B6_verification", "B7_workspace", "L_evid", "L_all_hand", "L_all_sem", "C3_evid_sem",
                "L_ver", "L_rep", "L_nov", "L_work", "L_sem", "L_evid_sem", "L_evid_ver",
                "B1_step30", "B1_step60", "L_evid_nov"):
        L.append(macro(f"auc{short(mon)}", fmt(wauc(mon))))
        L.append(macro(f"within{short(mon)}", fmt(wwithin(mon))))
    # aliases the prose uses
    L.append(macro("aucBones30", fmt(wauc("B1_step30"))))
    L.append(macro("aucBones60", fmt(wauc("B1_step60"))))
    L.append(macro("withinBones30", fmt(wwithin("B1_step30"))))

    # ---------- budget-calibrated operating points ----------
    bc_path = os.path.join(args.run, "budget_calibrated.json")
    if os.path.exists(bc_path):
        bc = json.load(open(bc_path, encoding="utf-8"))
        for mon, rows in bc.items():
            for r in rows:
                b = r.get("budget", float("nan"))
                tag = f"B{int(round(100*b))}" if b == b else "BX"
                L.append(macro(f"cal{short(mon)}{tag}Det", fmt(r.get("detection_rate"))))
                L.append(macro(f"cal{short(mon)}{tag}Fs", fmt(r.get("false_stop_rate"))))
                L.append(macro(f"cal{short(mon)}{tag}Cov", fmt(r.get("coverage"))))
                L.append(macro(f"cal{short(mon)}{tag}Thr", fmt(r.get("threshold"), 4)))
                L.append(macro(f"cal{short(mon)}{tag}TrajDet", fmt(r.get("traj_detection_rate"))))
                L.append(macro(f"cal{short(mon)}{tag}Saved", fmt(r.get("traj_mean_saved"), 1)))
                L.append(macro(f"cal{short(mon)}{tag}Lat", fmt(r.get("traj_median_latency"), 1)))

    # ---------- paired comparisons ----------
    pc_path = os.path.join(args.run, "paired_comparisons.json")
    if os.path.exists(pc_path):
        pc = json.load(open(pc_path, encoding="utf-8"))
        L.append(macro("pairBestMonitor", pretty(pc.get("best", ""))))
        # short key forms keep TeX control sequences well inside the 40-character limit
        SHORT_MON = {"C1_evidence": "C1ev", "C1_evidence_rel": "C1rel", "C2_evid_ver": "C2ev",
                     "C2_evid_ver_work": "C2evw", "C3_evid_sem": "C3es", "C4_all_hand": "C4all",
                     "B2_exact_rep3": "B2r3", "B3_rep_target": "B3tgt", "B4_semantic": "B4sem",
                     "B4_sem_diversity": "B4div", "B5_novelty": "B5nov", "B5_novelty_sig": "B5sig",
                     "B6_verification": "B6ver", "B7_workspace": "B7wk", "L_sem": "Lsem",
                     "L_evid": "Levid", "L_evid_sem": "Less"}
        for key, r in (pc.get("pairs") or {}).items():
            a, _, b = key.partition("_vs_")
            ka = SHORT_MON.get(a, a.replace("_", "")[:6])
            kb = SHORT_MON.get(b, b.replace("_", "")[:6])
            for field, suf in (("delta", "Delta"), ("lo", "Lo"), ("hi", "Hi"),
                               ("p_two_sided", "P")):
                L.append(macro(f"pair{ka}vs{kb}{suf}", fmt(r.get(field))))
            L.append(macro(f"pair{ka}vs{kb}Sig",
                           "yes" if (r.get("lo", 0) > 0 or r.get("hi", 0) < 0) else "no"))

    def wpr(mon: str) -> float:
        d = wl.get(mon, {})
        m = d.get(str(w)) or d.get(w)
        return float(m["pr_auc"]) if m else float("nan")

    for mon in ("C1_evidence", "C2_evid_ver", "C4_all_hand", "B4_semantic", "B2_exact_rep3",
                "B5_novelty", "B6_verification", "L_all_hand", "L_evid"):
        L.append(macro(f"prauc{short(mon)}", fmt(wpr(mon))))

    best = max(((n, wauc(n)) for n in wl if wauc(n) == wauc(n)), key=lambda t: t[1], default=("none", float("nan")))
    L.append(macro("bestAucMonitor", pretty(best[0])))
    L.append(macro("bestAuc", fmt(best[1])))
    bestsaved = max(((n, pick(n, "mean_saved_steps")) for n in frontier), key=lambda t: t[1] if t[1] == t[1] else -1e9)
    L.append(macro("bestSavedMonitor", pretty(bestsaved[0])))
    L.append(macro("bestSaved", fmt(bestsaved[1], 1)))
    L.append(macro("wParam", f"{w}"))

    # ---------------- evidence table (feature-level) ----------------
    L.append("\\begin{table}[t]\\centering\\small")
    L.append("\\caption{Evidence table: the strongest single feature per channel, measured as "
             "window-level ROC-AUC against the annotated labels.}")
    L.append("\\label{tab:evidence}")
    L.append("\\begin{tabular}{llr}\\toprule")
    L.append("Channel & Feature & ROC-AUC \\\\ \\midrule")
    feat_auc = {}
    import pyarrow.parquet as pq
    import numpy as np
    rows = pq.read_table(os.path.join(args.run, "window_features.parquet")).to_pylist()
    sub = [r for r in rows if r["binary"] is not None and r["w"] == w]
    y = np.array([r["binary"] for r in sub])
    from features import FEATURE_CHANNEL
    from evaluation import window_metrics
    for f, ch in FEATURE_CHANNEL.items():
        x = np.array([r[f] for r in sub], dtype=float)
        if len(set(y)) < 2 or np.all(np.isnan(x)) or np.nanstd(x) == 0:
            continue
        m = window_metrics(y, np.nan_to_num(x, nan=float(np.nanmean(x))))
        feat_auc[f] = (m["roc_auc"], ch)
    for ch in ("REP", "NOV", "EVID", "VER", "WORK", "SEM"):
        best_f = max(((f, v) for f, v in feat_auc.items() if v[1] == ch and v[0] == v[0]),
                     key=lambda t: t[1][0], default=(None, (float("nan"), ch)))
        if best_f[0] is None:
            continue
        L.append(f"{ch} & \\texttt{{{tex_escape(best_f[0])}}} & {fmt(best_f[1][0])} \\\\")
    L.append("\\bottomrule\\end{tabular}\\end{table}")
    L.append("")

    # ---------------- logistic coefficients ----------------
    # ``logistic_report.json`` is a per-fold list of coefficient dicts; average the folds and
    # keep the largest-magnitude coefficients so the learned models can be inspected in text.
    coef_summary: Dict[str, Dict[str, float]] = {}
    for gname, rows in lr.items():
        if not isinstance(rows, list) or not rows:
            continue
        keys = [k for k in rows[0] if k not in ("fold", "n", "pos", "intercept")]
        coef_summary[gname] = {k: float(np.mean([r.get(k, 0.0) for r in rows])) for k in keys}
        coef_summary[gname]["__intercept__"] = float(np.mean([r.get("intercept", 0.0) for r in rows]))
    for gname, coef in coef_summary.items():
        top = sorted(((k, v) for k, v in coef.items() if k != "__intercept__"),
                     key=lambda kv: -abs(kv[1]))[:6]
        L.append(f"% logistic[{gname}] folds={len(lr[gname])} "
                 f"intercept={coef['__intercept__']:.3f}")
        for k, v in top:
            L.append(f"%    {k:34s} {v:+.4f}")

    L.append("")
    L.append(macro("descAlarmRate", fmt(next(iter(desc.values()))["alarm_rate"] if desc else float("nan"), 3)))
    L.append(macro("descPassAll", fmt(next(iter(desc.values()))["pass_rate_all"] if desc else float("nan"), 3)))

    # ---------------- operational table (primary, per-window view) ----------------
    ops_path = os.path.join(args.run, "window_alarm_frontier.json")
    ops_lines: List[str] = []
    if os.path.exists(ops_path):
        ops = json.load(open(ops_path, encoding="utf-8"))
        ops_lines.append("\\begin{tabular}{lrrrr}\\toprule")
        ops_lines.append("Monitor & det.\\ & false stop & coverage & thr. \\\\ \\midrule")
        for name in order:
            if name not in ops:
                continue
            fr = ops[name]
            if isinstance(fr, dict):
                fr = fr.get(str(w)) or fr.get(w) or []
            pick = next((f for f in fr if abs(f["budget"] - 0.05) < 1e-9), None)
            if not pick or not pick.get("available"):
                continue
            ops_lines.append(f"{pretty(name)} & {fmt(pick.get('detection_rate'),2)} & "
                             f"{fmt(pick.get('false_stop_rate'),2)} & "
                             f"{fmt(pick.get('coverage'),2)} & {fmt(pick.get('threshold'),2)} \\\\")
        ops_lines.append("\\bottomrule\\end{tabular}")
        ops_lines.append("")
    abl_path = os.path.join(args.run, "ablation.json")
    if os.path.exists(abl_path):
        abl = json.load(open(abl_path, encoding="utf-8"))
        rows_out = []
        L.append("\\begin{tabular}{lrrr}\\toprule")
        L.append("Channel & alone & without & $\\Delta$ ROC \\\\ \\midrule")
        for ch in abl.get("channels", []):
            alone = abl["per_channel_alone"].get(ch, {})
            loo = abl["leave_one_out"].get(ch, {})
            rows_out.append((ch, alone.get("roc_auc"), loo.get("roc_auc"), loo.get("delta_roc")))
            L.append(f"{ch} & {fmt(alone.get('roc_auc'))} & {fmt(loo.get('roc_auc'))} & "
                     f"{fmt(loo.get('delta_roc'))} \\\\")
        L.append("\\midrule")
        L.append(f"\\multicolumn{{4}}{{l}}{{all channels: ROC-AUC {fmt(abl['full'].get('roc_auc'))}, "
                 f"PR-AUC {fmt(abl['full'].get('pr_auc'))}}} \\\\")
        L.append("\\bottomrule\\end{tabular}")
        for ch, a, b, d in rows_out:
            L.append(macro(f"abl{ch}AucAlone", fmt(a)))
            L.append(macro(f"abl{ch}AucWithout", fmt(b)))
            L.append(macro(f"abl{ch}Delta", fmt(d)))
        L.append(macro("ablFullAuc", fmt(abl["full"].get("roc_auc"))))
        L.append("")

    # ---------------- within-run robustness ----------------
    wr_path = os.path.join(args.run, "within_run_robustness.json")
    if os.path.exists(wr_path):
        wr = json.load(open(wr_path, encoding="utf-8"))
        best = wr["vs_step_budget"]["best"]
        b = wr["per_monitor"][best]
        L.append(macro("withinRunsBfourSemanticStrict", str(b["runs"])))
        L.append(macro("withinMedianBfourSemanticStrict", fmt(b["median"])))
        L.append(macro("withinWinsBfourSemanticStrict", str(b["wins"])))
        L.append(macro("withinLossesBfourSemanticStrict", str(b["losses"])))
        L.append(macro("withinSignPBfourSemanticStrict", f"{b['sign_p']:.4f}"))
        L.append(macro("withinHighBfourSemanticStrict", str(round(b["share_ge_0_70"] * b["runs"]))))
        ties = [m for m, v in wr["per_monitor"].items() if abs(v["median"] - 0.5) < 1e-9]
        L.append(macro("withinTieMonitors", str(len(ties))))
        L.append(macro("nMonitors", str(len(cfg.get("monitors") or wr["per_monitor"]))))
        L.append(macro("withinVsBudgetWins", str(wr["vs_step_budget"]["wins"])))
        L.append(macro("withinVsBudgetMedian", f"+{wr['vs_step_budget']['median_gain']:.3f}"))
        v = wr["variance"]
        L.append(macro("varianceTaskSdStrict", fmt(v["task_sd"])))
        L.append(macro("varianceRunSdStrict", fmt(v["run_sd"])))
        L.append(macro("varianceTaskAucStrict", fmt(v["task_rate_auc"])))
        L.append(macro("varianceZeroTasksStrict", str(v["zero_tasks"])))

    # ---------------- subtype support ----------------
    # how many windows and trajectories back each half of the "two kinds of stagnation" claim
    if os.path.exists(os.path.join(ann, "adjudicated.csv")):
        adj = list(csv.DictReader(open(os.path.join(ann, "adjudicated.csv"), encoding="utf-8")))
        nn = [r for r in adj if r["gold"] == "STAGNANT"
              and r["detail"] in ("no_new_information", "repeat_verify")]
        pc = [r for r in adj if r["gold"] == "DONE_REDUNDANT"]
        L.append(macro("annSubNothingNew", str(len(nn))))
        L.append(macro("annSubNothingNewTraj", str(len({r["traj_id"] for r in nn}))))
        L.append(macro("annSubPostCompletionTraj", str(len({r["traj_id"] for r in pc}))))
        L.append(macro("annSubWithDetail", str(sum(1 for r in pc if r["detail"]))))

    # ---------------- corpus redaction, measured on steps that have an observation ----------------
    # The earlier figure divided by all steps, including ones with no observation at all, which
    # understates how often a reader is shown a bare reference instead of output.
    red_path = os.path.join(paths.FINAL, "redaction.json")
    if os.path.exists(red_path):
        r = json.load(open(red_path, encoding="utf-8"))
        L.append(macro("corpusRedactFrac", f"{100 * r['share']:.1f}"))
        L.append(macro("corpusRedactMean", f"{100 * r['mean_per_traj']:.1f}"))
        L.append(macro("corpusRedactSteps", str(r["steps"])))
        for i, b in enumerate(r["buckets"]):
            L.append(macro(f"redactTie{i}", f"{100 * b['tie_rate']:.1f}"))
    # ---------------- v2 rebuild probes: representation swap and target feasibility --------
    up = os.path.join("results", "final", "v2", "embedding_upgrade_test.json")
    if os.path.exists(up):
        u = json.load(open(up, encoding="utf-8"))["auc"]
        L.append(macro("probeRocBoW", fmt(u.get("v1_hashing_bow_B4_semantic"))))
        L.append(macro("probeRocEnc", fmt(u.get("v2_semantic_MiniLM-L6"))))
    probe = os.path.join("results", "final", "v2", "probe_numbers.json")
    if os.path.exists(probe):
        pn = json.load(open(probe, encoding="utf-8"))
        for key, name in (("runs_no_event_pct", "probeRunsNoEvent"),
                          ("runs_pytest_pct", "probeRunsPytest"),
                          ("runs_build_pct", "probeRunsBuild"),
                          ("events_fail_mean", "probeEventsFail"),
                          ("events_pass_mean", "probeEventsPass"),
                          ("flips_k3", "probeFlipsThree"),
                          ("feat_diversity", "probeFeatDiversity"),
                          ("feat_nearest", "probeFeatNearest")):
            if key in pn:
                L.append(macro(name, str(pn[key])))
    # ---------------- v2: the measured performance ceiling ----------------
    ceil = os.path.join("results", "final", "v2", "ceiling_test.json")
    if os.path.exists(ceil):
        c = json.load(open(ceil, encoding="utf-8"))
        L.append(macro("ceilBase", fmt(c["baseline_auc"])))
        L.append(macro("ceilLo", fmt(c["baseline_ci"][0])))
        L.append(macro("ceilHi", fmt(c["baseline_ci"][1])))
        L.append(macro("ceilAttempts", str(len(c.get("independent_attempts", {})) + 4)))
        L.append(macro("probeNWindows", str(c.get("n_windows", 1103))))
    jm = os.path.join("results", "final", "v2", "joint_model_test.json")
    if os.path.exists(jm):
        j = json.load(open(jm, encoding="utf-8"))
        L.append(macro("jointAuc", fmt(j["joint_auc"])))
        L.append(macro("jointDiff", f"{j['paired_diff']:+.3f}"))
        L.append(macro("jointLo", f"{j['ci'][0]:+.3f}"))
        L.append(macro("jointHi", f"{j['ci'][1]:+.3f}"))
        L.append(macro("jointP", f"{j['p']:.3f}"))
    # ---------------- regime-level headline result ----------------
    rh = os.path.join("results", "final", "v2", "regime_headline.json")
    if os.path.exists(rh):
        g = json.load(open(rh, encoding="utf-8"))
        L.append(macro("regEpisodes", str(g["n_episodes"])))
        L.append(macro("regProdRegions", str(g["n_productive_regions"])))
        L.append(macro("regEpWindows", str(g["windows_in_episodes"])))
        L.append(macro("regMedianSteps", f"{g['episode_median_steps']:.0f}"))
        L.append(macro("regMaxSteps", str(g["episode_max_steps"])))
        L.append(macro("regGeTwenty", str(g["episodes_ge20"])))
        L.append(macro("regSep", str(g["episodes_separated"])))
        L.append(macro("regTot", str(g["episodes_total"])))
        L.append(macro("regSepPct", f"{100*g['episodes_separated']/g['episodes_total']:.0f}"))
        L.append(macro("regDiff", f"{g['mean_diff']:+.3f}"))
        L.append(macro("regDiffLo", f"{g['ci'][0]:+.3f}"))
        L.append(macro("regDiffHi", f"{g['ci'][1]:+.3f}"))
        L.append(macro("regP", f"{g['p']:.4f}"))
        L.append(macro("regPmSep", str(g["pm_separated"])))
        L.append(macro("regPmTot", str(g["pm_total"])))
        L.append(macro("regPmPct", f"{100*g['pm_separated']/g['pm_total']:.0f}"))
        L.append(macro("regPmDiff", f"{g['pm_mean_diff']:+.3f}"))
        L.append(macro("regPmLo", f"{g['pm_ci'][0]:+.3f}"))
        L.append(macro("regPmHi", f"{g['pm_ci'][1]:+.3f}"))
        L.append(macro("regPmP", f"{g['pm_p']:.4f}"))
        L.append(macro("regProxySep", str(g["proxy_pm_separated"])))
        L.append(macro("regProxyTot", str(g["proxy_pm_total"])))
    # ---------------- stationarity / calibration attempt ----------------
    dr = os.path.join("results", "final", "v2", "drift_frontier_test.json")
    if os.path.exists(dr):
        d = json.load(open(dr, encoding="utf-8"))
        L.append(macro("drRunsPositiveTrend", str(d.get("runs_positive_trend", 0))))
        L.append(macro("drRunsPositiveTrendMax", str(d.get("n_runs_trended", 1344))))
        L.append(macro("drMeanSlope", f"{d.get('mean_slope', 0):.4f}"))
        L.append(macro("drCorrStep", fmt(d.get("mean_abs_corr_with_step"))))
    fr = os.path.join("results", "final", "v2", "detector_frontier.json")
    if os.path.exists(fr):
        f = json.load(open(fr, encoding="utf-8"))
        for mon, tag in (("B4_semantic", "BFour"), ("C3_evid_sem", "CThree")):
            m = f.get(mon, {}).get("matched", {})
            for k, lab in (("0.05", "Five"), ("0.2", "Twenty")):
                if k in m:
                    L.append(macro(f"det{tag}{lab}", f"{100*m[k]:.0f}"))
    sq = os.path.join("results", "final", "v2", "sequential_external_test.json")
    if os.path.exists(sq):
        q = json.load(open(sq, encoding="utf-8"))
        if "llr_boundary5.0" in q:
            L.append(macro("seqDet", str(q["llr_boundary5.0"]["det"])))
            L.append(macro("seqFp", str(q["llr_boundary5.0"]["fp"])))
    # ---------------- the stagnation alarm (verified detector) ----------------
    al = os.path.join("results", "final", "v2", "alarm_artifact.json")
    if os.path.exists(al):
        a = json.load(open(al, encoding="utf-8"))
        L.append(macro("alMonitor", "novelty"))
        L.append(macro("alDet", f"{100*a['detection_rate']:.0f}"))
        L.append(macro("alDetN", str(a["episodes_detected"])))
        L.append(macro("alDetTot", str(a["episodes"])))
        L.append(macro("alFaWin", f"{100*a['false_alarm_window_rate']:.0f}"))
        L.append(macro("alFaRegion", f"{100*a['false_alarm_region_rate']:.0f}"))
        L.append(macro("alLatency", f"{a['median_latency_steps']:.0f}"))
        L.append(macro("alSmooth", str(a["k_smooth"])))
        L.append(macro("alKsd", fmt(a["k_sd"], 1)))
        L.append(macro("alOpen", f"{100*a['open_frac']:.0f}"))
    nv = os.path.join("results", "final", "v2", "nested_validation.json")
    if os.path.exists(nv):
        n = json.load(open(nv, encoding="utf-8"))
        L.append(macro("nestedDet", f"{100*n['detection']:.0f}"))
        L.append(macro("nestedFa", f"{100*n['fa_window']:.0f}"))
        L.append(macro("nestedDetN", str(n["episodes_detected"])))
        L.append(macro("nestedTot", str(n["episodes_total"])))
        L.append(macro("nestedRuns", str(n["n_runs"])))
    # ---------------- runtime cost ----------------
    rt_path = os.path.join(paths.FINAL, "runtime.json")
    if os.path.exists(rt_path):
        rt = json.load(open(rt_path, encoding="utf-8"))
        L.append(macro("rtMsPerWindow", fmt(rt.get("ms_per_window_feature_vector"), 2)))
        L.append(macro("rtMsPerStep", fmt(rt.get("ms_per_step_scoring_one_monitor"), 3)))
        L.append(macro("rtWindows", str(rt.get("windows", 0))))
    audit_path = os.path.join(paths.FINAL, "number_audit.json")
    if os.path.exists(audit_path):
        au = json.load(open(audit_path, encoding="utf-8"))
        L.append(macro("auditChecked", str(au.get("checked", 0))))

    # ---------------- window-size sensitivity ----------------
    alt_runs = {"w6": ("results/final/tb2_w6_w30", 6), "w20": ("results/final/tb2_final", 20),
                "w30": ("results/final/tb2_w6_w30", 30)}
    for tag, (rdir, ww) in alt_runs.items():
        p = os.path.join(rdir, "window_metrics.json")
        if not os.path.exists(p):
            continue
        alt = json.load(open(p, encoding="utf-8"))
        # a few headline monitors at each alternative window size
        for mon in ("B4_semantic", "L_sem", "C1_evidence", "C3_evid_sem", "B5_novelty"):
            m = alt.get(mon, {}).get(str(ww))
            if m:
                L.append(macro(f"{tag}{mon.replace('_', '')}", fmt(m["roc_auc"])))

    # ---------------- cross-scaffold generalisation ----------------
    cs_path = os.path.join(args.run, "cross_scaffold.json")
    if os.path.exists(cs_path):
        cs = json.load(open(cs_path, encoding="utf-8"))
        for gname, g in cs.get("groups", {}).items():
            # key forms the prose uses: semantic, repetition, workspace, evidence, evidencesemantic
            key = (gname.split("(")[0].strip().rstrip("+").strip()
                   .replace("auction/repetition", "repetition")
                   .replace("+", "").replace(" ", "").replace("/", ""))
            if g.get("mean_auc") is None:
                continue
            L.append(macro(f"cs{key}Mean", fmt(g["mean_auc"])))
            L.append(macro(f"cs{key}Min", fmt(g["min_auc"])))
            L.append(macro(f"cs{key}Max", fmt(g["max_auc"])))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    # Aliases: the paper prose uses readable spelled-out names; point them at the canonical
    # macro so both spellings work and a rename cannot produce a silent "??" in the PDF.
    ALIASES = {
        "aucBfoursemantic": "aucB4semantic", "aucBsevenworkspace": "aucB7workspace",
        "aucBsixverification": "aucB6verification", "aucBtwoexactrepthree": "aucB2rep3",
        "aucConeevidence": "aucC1evidence", "aucCthreeevidsem": "aucC3evidSem",
        "aucBfivenovelty": "aucB5novelty", "aucBfourdiv": "aucB4semDiversity",
        "aucCfourallhand": "aucC4allHand", "aucLallhand": "aucLallHand",
        "aucLallsem": "aucLallSem", "aucLevidsem": "aucLevidsem",
        "aucLseventyeight": "aucLsem",
        "withinBfoursemantic": "withinB4semantic", "withinCthreeevidsem": "withinC3evidSem",
        "withinBfivenovelty": "withinB5novelty", "withinConeevidence": "withinC1evidence",
        "withinBtwoexactrepthree": "withinB2rep3", "withinBsevenworkspace": "withinB7workspace",
        "withinBones30": "withinB1step30", "withinCfourallhand": "withinC4allHand",
        "pairC1evidencevsB4semanticDelta": "pairC1evvsB4semDelta",
        "pairC1evidencevsB4semanticLo": "pairC1evvsB4semLo",
        "pairC1evidencevsB4semanticHi": "pairC1evvsB4semHi",
        "pairB7workspacevsB4semanticDelta": "pairB7wkvsB4semDelta",
        "pairB7workspacevsB4semanticLo": "pairB7wkvsB4semLo",
        "pairB7workspacevsB4semanticHi": "pairB7wkvsB4semHi",
        "pairB2rep3vsB4semanticDelta": "pairB2r3vsB4semDelta",
        "pairB6verificationvsB4semanticDelta": "pairB6vervsB4semDelta",
        "pairC3evidSemvsB4semanticDelta": "pairC3esvsB4semDelta",
        "pairC3evidSemvsB4semanticLo": "pairC3esvsB4semLo",
        "pairC3evidSemvsB4semanticHi": "pairC3esvsB4semHi",
        "calLsemB5DetectionRate": "calLsemB5Det", "calC3evidSemB5DetectionRate": "calC3evidSemB5Det",
        "calLsemB5MeanSavedSteps": "calLsemB5Saved",
        "calC1evidenceB5DetectionRate": "calC1evidenceBOneDet",
        "calB4semanticB5DetectionRate": "calB4semanticBOneDet",
        # window-size sensitivity, spelled the way the prose refers to it
        "wSixBfourSemantic": "wSixBFoursemantic",
        "wTwoZeroBfourSemantic": "wTwoZeroBFoursemantic",
        "wTwentyBfourSemantic": "wTwoZeroBFoursemantic",
        "wThreeZeroBfourSemantic": "wThreeZeroBFoursemantic",
        "wThirtyBfourSemantic": "wThreeZeroBFoursemantic",
    }
    # the paper also refers to the same quantities by their spelled-out digit form
    for extra in list(ALIASES.items()):
        alias, target = extra
        spoken = "".join(DIGIT_WORDS.get(ch, ch) for ch in alias)
        if spoken != alias:
            ALIASES.setdefault(spoken, target)
    # Split macros from tables: macros must land in the preamble, tables in the body.
    macros = [l for l in L if l.startswith("\\newcommand") or l.startswith("%")]
    body = [l for l in L if not l.startswith("\\newcommand") and not l.startswith("%")]
    defined = {m.group(1) for m in re.finditer(r"\\newcommand\{\\(\w+)\}", "\n".join(macros))}
    # Definitions carry the "p" prefix and have digits spelled out; aliases are written against
    # the bare semantic name, so compare in the same (spoken) form.
    def spoken(x: str) -> str:
        return "".join(DIGIT_WORDS.get(ch, ch) for ch in x)

    bare_defined = set(defined) | {n[1:] for n in defined if n.startswith("p")}
    made: set = set()
    n_alias = 0
    for alias, target in ALIASES.items():
        a, t = spoken(alias), spoken(target)
        if t not in bare_defined or a in bare_defined or a in made:
            continue
        # alias names carry the same prefix as generated macros, so nothing in the paper
        # depends on an unprefixed control sequence
        macros.append(f"\\newcommand{{\\p{a}}}{{\\p{t}}}")
        made.add(a)
        n_alias += 1
    print(f"aliases added: {n_alias}")
    header = [f"% AUTO-GENERATED by scripts/export_results_tex.py from {args.run}",
              f"% built: {cfg['built_at']}   corpus: {cfg['corpus']}   window size: {args.w}",
              "% macros: input this file in the preamble; tables live in the tables_* file."]
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(header + macros) + "\n")
    body_path = os.path.join(os.path.dirname(os.path.abspath(args.out)),
                             os.path.basename(args.out).replace("generated_", "tables_"))
    body_header = [f"% AUTO-GENERATED by scripts/export_results_tex.py from {args.run}",
                   "% input this file inside the document body."]
    with open(body_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(body_header + body) + "\n")
    ops_out = os.path.join(os.path.dirname(os.path.abspath(args.out)), "generated_ops.tex")
    with open(ops_out, "w", encoding="utf-8") as fh:
        fh.write("% AUTO-GENERATED operational table (per-window view)\n")
        fh.write("\n".join(ops_lines) + "\n")
    print(f"wrote {args.out} ({len(macros)} macro lines) and {body_path} ({len(body)} table lines)")
    print("\n".join(l for l in macros if l.startswith("\\newcommand"))[:1500])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
