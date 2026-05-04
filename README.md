# STL Tutor

An adaptation of [LTL Tutor](https://github.com/brownplt/LTLTutor) to teach STL concepts instead.

To install and run, follow the Development Environment instructions found in [AGENTS.md](AGENTS.md)

STL Tutor is currently incomplete. As it is now, there is are equivalent classes to ltlnode.py and ltltoeng.py for STL. These can be found in [src/stl](src/stl). The STL syntax was copied from [PyTeLo](https://github.com/erl-lehigh/PyTeLo/tree/main).

# Missing Features:
- Convert to using Signals
  - Traces
    - LTLTutor uses Traces, stored as strings, as the accepting objects for LTL formulas
    - Traces are displayed as a series of discrete boolean values
    - Satisfaction is determined using SPOT
  - Signals
    - Signals are a continuous series of values and as such require a more complete representation than LTL Traces
    - Signals would also require a different display method from Traces
    - Satisfaction can be determined using PyTeLo, but would require converting to their data structures

- Distractor Generation
  - At the core of LTLTutor is its ability to generate "Distractors" i.e. similar looking, but invalid answers to their problems
  - Generated via "Misconceptions" that are common LTL mistakes, not STL mistakes
  - Leverages SPOT to generate random LTL formulas
  - Additionally leverage SPOT to make sure generated formulas aren't equivalent to the correct formula

# Potential Areas for Improvement:
- Robustness
  - Robustness is a very central concept to STL, but isn't covered by LTL
  - No problem structures test Robustness knowledge
  - Robustness should be included in an STL focused learning tool

- STL to English
  - English phrases for STL structures were done by adapting the existing strucutre that were targetted for LTL
  - Its likely that what sounds natural for an LTL formula does not map cleanly to an STL formula
  - Its also likely that some specific patterns that were found in LTL to want specific verbiage would not be wanted in STL or vice versa