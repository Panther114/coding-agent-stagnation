"""agentstall: online progress/stagnation study, v2.

The first version of this study (``src/features.py`` and friends) is frozen and left
untouched.  This package is the rebuild: one per-step table over *both* corpora on
disk, objective (non-judged) outcome fields, and a monitor designed to be stationary
within a run.

Modules
-------
corpus   loaders and outcome parsing for Terminal-Bench 2.0 and Nebius SWE-agent
features online window features, in raw and position-normalised forms
targets  objective progress labels mined from the corpus itself
"""
__all__ = ["corpus", "features", "targets"]
