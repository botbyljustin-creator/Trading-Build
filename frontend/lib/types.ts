// Mirrors the Pydantic response schemas in backend/app/api/routes/*.py —
// kept hand-written rather than codegen'd for now; if the two drift, the
// browser network tab / TypeScript errors surface it quickly since every
// page reads through these types.

export type SourceType = "YOUTUBE_VIDEO" | "YOUTUBE_PLAYLIST" | "YOUTUBE_CHANNEL";
export type SourceStatus = "PENDING" | "RESOLVING" | "READY" | "FAILED";
export type TranscriptStatus = "PENDING" | "AVAILABLE" | "TRANSCRIPT_UNAVAILABLE" | "FAILED";

export type RuleCategory =
  | "MARKET"
  | "TIMEFRAME"
  | "SESSION"
  | "MARKET_REGIME"
  | "BIAS"
  | "SETUP"
  | "ENTRY"
  | "CONFIRMATION"
  | "STOP_LOSS"
  | "TAKE_PROFIT"
  | "POSITION_SIZING"
  | "TRADE_MANAGEMENT"
  | "INVALIDATION"
  | "NO_TRADE_CONDITIONS";

export type RuleStatus =
  | "EXTRACTED"
  | "AMBIGUOUS"
  | "CONTRADICTORY"
  | "USER_CONFIRMED"
  | "USER_MODIFIED"
  | "AI_ASSUMPTION"
  | "REJECTED";

export type ContradictionResolution = "UNRESOLVED" | "USE_A" | "USE_B" | "CONTEXT_DEPENDENT" | "IGNORE";
export type StrategyVersionStatus = "DRAFT" | "COMPILED" | "ARCHIVED";
export type CodeLanguage = "PINE" | "PYTHON";
export type JobType =
  | "INGEST_SOURCE"
  | "FETCH_TRANSCRIPT"
  | "EXTRACT_CONCEPTS"
  | "EXTRACT_RULES"
  | "DETECT_CONTRADICTIONS"
  | "COMPILE_STRATEGY"
  | "GENERATE_CODE"
  | "RUN_BACKTEST"
  | "RUN_ROBUSTNESS"
  | "GENERATE_REPORT";
export type JobStatus = "PENDING" | "RUNNING" | "SUCCESS" | "FAILED";
export type BacktestStatus = "PENDING" | "RUNNING" | "COMPLETE" | "FAILED";
export type OverfittingRisk = "LOW" | "MEDIUM" | "HIGH";
export type TradeDirection = "LONG" | "SHORT";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  job_type: JobType;
  status: JobStatus;
  progress_pct: number;
  progress_message: string | null;
  result_ref: Record<string, unknown> | null;
  error_message: string | null;
}

export interface Series {
  id: string;
  creator_name: string;
  series_name: string;
  youtube_playlist_id: string | null;
  description: string | null;
  video_count: number;
}

export interface SourceRecord {
  id: string;
  source_type: SourceType;
  url: string;
  title: string | null;
  status: SourceStatus;
  error_message: string | null;
  estimated_video_count: number | null;
  estimated_transcript_tokens: number | null;
  estimated_cost_usd: number | null;
  created_at: string;
}

export interface VideoRecord {
  id: string;
  series_id: string | null;
  position_in_series: number | null;
  youtube_video_id: string;
  title: string;
  channel_name: string | null;
  publish_date: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  url: string;
  transcript_status: TranscriptStatus;
  is_manual_import: boolean;
  transcript_error: string | null;
}

export interface ConceptSource {
  id: string;
  video_id: string;
  start_seconds: number;
  end_seconds: number;
  excerpt: string;
}

export interface Concept {
  id: string;
  name: string;
  description: string;
  confidence: number;
  instrument_tags: string[];
  created_at: string;
  sources: ConceptSource[];
}

export interface RuleSource {
  id: string;
  video_id: string;
  start_seconds: number;
  end_seconds: number;
  excerpt: string;
}

export type RuleEvidenceType = "EXPLICIT" | "IMPLIED" | "DISCRETIONARY" | "USER_DEFINED" | "AI_ASSUMPTION";
export type Quantifiability = "FULLY_QUANTIFIABLE" | "PARTIALLY_QUANTIFIABLE" | "DISCRETIONARY";

export interface Rule {
  id: string;
  series_id: string | null;
  category: RuleCategory;
  natural_language_rule: string;
  machine_readable_rule: Record<string, unknown> | null;
  confidence: number;
  status: RuleStatus;
  evidence_type: RuleEvidenceType;
  quantifiability: Quantifiability | null;
  instrument_tags: string[];
  is_user_provided: boolean;
  user_note: string | null;
  created_at: string;
  sources: RuleSource[];
}

export interface Contradiction {
  id: string;
  rule_a_id: string;
  rule_b_id: string;
  explanation: string;
  resolution: ContradictionResolution;
  created_at: string;
}

export interface StrategyVersion {
  id: string;
  version_number: number;
  label: string | null;
  change_summary: string | null;
  status: StrategyVersionStatus;
  completeness_score: number | null;
  missing_fields: string[] | null;
  rule_ids: string[];
  created_at: string;
}

export interface Strategy {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  created_at: string;
  versions: StrategyVersion[];
}

export interface GeneratedCodeRow {
  language: CodeLanguage;
  code: string;
  spec_hash: string;
}

export interface BacktestMetrics {
  net_profit: number;
  total_return_pct: number;
  cagr_pct: number | null;
  max_drawdown_pct: number;
  profit_factor: number | null;
  win_rate_pct: number;
  avg_win: number;
  avg_loss: number;
  win_loss_ratio: number | null;
  expectancy: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  num_trades: number;
  avg_trade: number;
  largest_win: number;
  largest_loss: number;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  avg_holding_period_minutes: number;
  equity_curve: { timestamp: string; equity: number }[];
  drawdown_curve: { timestamp: string; drawdown_pct: number }[];
  monthly_returns: Record<string, number>;
  long_stats: { num_trades: number; win_rate_pct: number; net_profit: number };
  short_stats: { num_trades: number; win_rate_pct: number; net_profit: number };
}

export interface Trade {
  direction: TradeDirection;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  stop_price: number;
  target_price: number | null;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  r_multiple: number;
  exit_reason: string;
}

export interface Backtest {
  id: string;
  strategy_version_id: string;
  provider: string;
  symbol: string;
  timezone: string;
  asset_type: string;
  date_start: string;
  date_end: string;
  starting_balance: number;
  status: BacktestStatus;
  error_message: string | null;
  assumptions_notes: string | null;
  created_at: string;
  metrics: BacktestMetrics | null;
  trades: Trade[];
}

export interface OptimizationRun {
  id: string;
  run_type: string;
  results: Record<string, unknown>;
  overfitting_risk: OverfittingRisk | null;
  overfitting_reasons: string[] | null;
}

export interface Report {
  id: string;
  strategy_version_id: string;
  backtest_id: string | null;
  content_json: Record<string, unknown>;
  created_at: string;
}
