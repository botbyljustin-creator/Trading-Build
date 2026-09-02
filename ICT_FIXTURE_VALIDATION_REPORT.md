```
==============================================================================
ICT PIPELINE VALIDATION REPORT — [SYNTHETIC FIXTURE] ICT Pipeline Validation Set
==============================================================================

1. VIDEOS INGESTED
  - [SYNTHETIC FIXTURE] Market Structure Judgment Calls  [series: ICT Mentorship 2022 (SYNTHETIC FIXTURE)]  transcript_status=AVAILABLE
  - [SYNTHETIC FIXTURE] Optimal Trade Entry — 2016 model  [series: ICT 2016 Concepts (SYNTHETIC FIXTURE)]  transcript_status=AVAILABLE
  - [SYNTHETIC FIXTURE] Optimal Trade Entry — 2022 model  [series: ICT Mentorship 2022 (SYNTHETIC FIXTURE)]  transcript_status=AVAILABLE
  - [SYNTHETIC FIXTURE] Order Blocks & Fair Value Gaps  [series: ICT Mentorship 2022 (SYNTHETIC FIXTURE)]  transcript_status=AVAILABLE

2. CONCEPTS EXTRACTED
  - Order Block  (confidence=0.85, instrument_tags=[], sources=1)
  - Fair Value Gap  (confidence=0.85, instrument_tags=[], sources=1)
  - Optimal Trade Entry (2022 model)  (confidence=0.80, instrument_tags=[], sources=1)
  - Optimal Trade Entry (2016 model)  (confidence=0.75, instrument_tags=[], sources=1)

3. EXECUTABLE RULES (EXPLICIT + FULLY or PARTIALLY QUANTIFIABLE)
  - [ENTRY] Enter long when price returns into a bullish Fair Value Gap formed during the London or New York kill zone, provided a bullish order block sits below it, on NASDAQ NQ.
      series=ICT Mentorship 2022 (SYNTHETIC FIXTURE)  quantifiability=PARTIALLY_QUANTIFIABLE  instrument_tags=['NQ']
  - [ENTRY] Enter within the 62% to 79% Fibonacci retracement zone of the most recent dealing-range swing before continuation.
      series=ICT Mentorship 2022 (SYNTHETIC FIXTURE)  quantifiability=FULLY_QUANTIFIABLE  instrument_tags=[]
  - [ENTRY] Enter within the 70% to 88% retracement zone of the prior dealing-range swing.
      series=ICT 2016 Concepts (SYNTHETIC FIXTURE)  quantifiability=FULLY_QUANTIFIABLE  instrument_tags=[]

4. DISCRETIONARY / AI_ASSUMPTION RULES (never auto-enter a backtest without approval)
  - [CONFIRMATION] evidence_type=AI_ASSUMPTION status=AI_ASSUMPTION
      "Inferred: prefer the Fair Value Gap closest to a freshly formed order block over older, previously mitigated imbalances."
      series=ICT Mentorship 2022 (SYNTHETIC FIXTURE)  quantifiability=DISCRETIONARY
  - [SETUP] evidence_type=DISCRETIONARY status=EXTRACTED
      "Wait for a clear shift in market structure, judged by eye rather than a fixed candle count or price threshold, before considering an entry."
      series=ICT Mentorship 2022 (SYNTHETIC FIXTURE)  quantifiability=DISCRETIONARY

5. CONTRADICTIONS DISCOVERED
  - Rule A [ICT Mentorship 2022 (SYNTHETIC FIXTURE)]: Enter within the 62% to 79% Fibonacci retracement zone of the most recent dealing-range swing before continuation.
    Rule B [ICT 2016 Concepts (SYNTHETIC FIXTURE)]: Enter within the 70% to 88% retracement zone of the prior dealing-range swing.
    Explanation: Two different Optimal Trade Entry retracement ranges are taught across series: 62%-79% (2022 model) vs 70%-88% (2016 model). This reflects the teaching evolving over time, not the same rule stated twice — they must not be silently merged into one.
    Resolution: UNRESOLVED (unresolved until a human decides)

6. MODEL MOST SUITABLE FOR FIRST NASDAQ BACKTEST
  Candidate: the 'ICT Mentorship 2022 (SYNTHETIC FIXTURE)' Order Block + Fair Value Gap entry model.
    - Has an EXPLICIT, PARTIALLY_QUANTIFIABLE ENTRY rule tagged for NQ.
    - Formal Model Backtest Readiness Score (source support / quantifiability / rule
      completeness / NASDAQ relevance) is not yet implemented (tracked separately) — this
      is a qualitative read of the same signals it will use.

7. WHAT REMAINS BEFORE THAT BACKTEST CAN RUN
  - Replace this synthetic fixture with real ICT transcripts via manual import (or lift the
    network block) so extraction runs against actual source material.
  - The Order Block/FVG model above has no stop-loss, take-profit, or position-sizing rule
    yet — the Strategy Auditor (completeness check) must flag these as missing rather than
    inventing them.
  - Build the formal Model Backtest Readiness Score and the quantification workflow so a
    PARTIALLY_QUANTIFIABLE rule like the kill-zone entry above gets an explicit, user-approved
    numeric definition before it can compile.
  - Compile a StrategySpecification from the approved rule set and run it through the
    existing (already-built) backtest engine against real NQ/US100 historical data.

8. SEARCH SANITY CHECK (same code path exposed via /search)
  - [TRANSCRIPT] [SYNTHETIC FIXTURE] Order Blocks & Fair Value Gaps: 1 citation(s)
  - [CONCEPT] Order Block: 1 citation(s)
  - [RULE] ENTRY: 1 citation(s)
  - [RULE] CONFIRMATION: 1 citation(s)
==============================================================================
```
