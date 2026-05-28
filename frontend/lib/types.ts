// Mirror of backend Pydantic response shapes. Only fields rendered in the UI
// are typed; the rest stay loose to avoid duplicating every schema.

export type DolLifecycle =
  | "Active"
  | "Weakening"
  | "Shift Pending"
  | "Shift Confirmed"
  | "Completed"
  | "Invalidated";

export interface MarketSnapshot {
  id: number;
  symbol: string;
  timeframe: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string | null;
  timestamp_utc: string;
  timestamp_ny: string;
  session: string;
  session_anchor: string;
  daily_quarter: string;
  micro_quarter_90m: string;
  day_of_week: string;
  is_killzone: boolean;
}

export interface LiquidityLevel {
  id: number;
  symbol: string;
  level_type: string;
  liquidity_side: string;
  price: string;
  status: string;
  source_timeframe: string;
  status_reason: string;
}

export interface DolObjective {
  level_id: number;
  level_type: string;
  liquidity_side: string;
  price: string;
  liquidity_status: string;
}

export interface DolResponse {
  id: number;
  symbol: string;
  lifecycle_status: DolLifecycle;
  delivery_direction: string | null;
  primary_dol: DolObjective | null;
  secondary_dol: DolObjective | null;
  htf_objective: DolObjective | null;
  intraday_objective: DolObjective | null;
  engineered_liquidity: DolObjective | null;
  source_sweep_event_id: number | null;
  objective_quality: string | null;
  status_reason: string;
  execution_status: string;
  as_of_utc: string;
}

export interface ImbalanceZone {
  poi_id: number;
  poi_type: string;
  timeframe: string;
  direction: string;
  price_low: string;
  price_high: string;
  status: string;
}

export interface MappingLayer {
  narrative_timeframe: string;
  direction_timeframes: string[];
  irl: unknown | null;
  erl: unknown | null;
  direction_liquidity: string;
  status: string;
  reason: string;
  imbalance: ImbalanceZone | null;
}

export interface IrlErlMappingResponse {
  id: number;
  symbol: string;
  direction_flow: string;
  mapping_status: string;
  layers: MappingLayer[];
  conflict_flags: string[];
  limitations: string[];
  status_reason: string;
  execution_status: string;
  imbalance: ImbalanceZone | null;
  imbalance_role: string | null;
}

export interface QuarterReadinessResponse {
  id: number;
  symbol: string;
  daily_quarter: string;
  micro_quarter_90m: string;
  quarter_status: string;
  session: string;
  session_anchor: string;
  quarter_intent: string;
  manipulation_status: string;
  expansion_status: string;
  quarter_execution_allowed: boolean;
  gate_decision: string;
  status_reason: string;
  next_valid_window: string;
  source_sweep_event_id: number | null;
  as_of_utc: string;
}

export interface SsmtResponse {
  id: number;
  trade_asset: string;
  confirmation_symbol: string;
  ssmt_status: string;
  direction: string | null;
  xau_relative_state: string;
  cic_detected: boolean;
  quarter_sequence_valid: boolean;
  first_quarter: string | null;
  second_quarter: string | null;
  magneto_status: string;
  poi_touched: boolean;
  poi_reference: string | null;
  algorithm_context_status: string;
  ssmt_dol_alignment: string;
  ssmt_noise_status: string;
  confirmation_pair_state: string;
  liquidity_context: string;
  status_reason: string;
}

export interface NarrativeSnapshot {
  id: number;
  symbol: string;
  session: string;
  session_anchor: string;
  daily_quarter: string;
  quarter_status: string;
  next_valid_window: string;
  htf_dol: string;
  dol_status: string;
  direction_liquidity: string;
  active_model: string;
  macro_state: string;
  quarterly_state: string;
  session_state: string;
  intraday_state: string;
  conflict_resolution: string;
  news_catalyst_status: string;
  delivery_tempo: string;
  delivery_state: string;
  session_narrative: string;
  judas_manipulation_status: string;
  opr_status: string;
  mmxm_timing_context: string;
  ssmt_status: string;
  expansion_quality: string;
  setup_context: string;
  trigger_confirmation: string;
  risk_context: string;
  execution_status: string;
  no_trade_reason: string;
  validation_required: string;
  continuation_status: string;
  reset_required: boolean;
  next_decision_if_invalidated: string;
  invalidation: string;
  target_liquidity: string;
  retracement_reference: string;
  rendered_snapshot: string;
  telegram_status: string;
  telegram_message_id: string | null;
  as_of_utc: string;
  created_at: string;
}

export interface AlertRecord {
  id: number;
  event_type: string;
  symbol: string;
  message: string;
  severity: string;
  sent_to_telegram: boolean;
  created_at: string;
}

export interface JournalEntry {
  id: number;
  symbol: string;
  setup_context: string;
  entry_reason: string;
  execution_confirmation: string;
  risk: string | null;
  result: string | null;
  mistake_review: string | null;
  narrative_review: string | null;
  screenshot_path: string | null;
  created_at: string;
}

export interface BacktestRun {
  id: number;
  symbol: string;
  timeframe: string;
  status: string;
  narrative_samples: number;
  scored_samples: number;
  valid_setup_samples: number;
  setup_wins: number;
  setup_losses: number;
  winrate: string | null;
  average_rr: string | null;
  max_drawdown_rr: string | null;
  no_trade_accuracy: string | null;
  false_ssmt_rate: string | null;
  false_sweep_rate: string | null;
  best_session: string | null;
  worst_session: string | null;
  best_quarter: string | null;
  worst_quarter: string | null;
  created_at: string;
}

export interface IngestionRun {
  provider: string;
  symbol: string;
  timeframe: string;
  status: string;
  candles_fetched: number;
  candles_inserted: number;
  candles_skipped: number;
  first_candle_utc: string | null;
  last_candle_utc: string | null;
  started_at_utc: string;
  finished_at_utc: string;
  error_message: string | null;
}

export interface SchedulerStatus {
  running: boolean;
  provider: string | null;
  symbols: string[];
  timeframes: string[];
  interval_seconds: number | null;
  last_tick_utc: string | null;
  last_error: string | null;
  next_tick_utc: string | null;
}

export interface EconomicEvent {
  id: number;
  provider: string;
  event_name: string;
  country: string;
  impact: string;
  scheduled_at_utc: string;
  actual: string | null;
  forecast: string | null;
  previous: string | null;
  is_relevant: boolean;
}

export interface ReplayRun {
  id: number;
  symbol: string;
  timeframe: string;
  policy_name: string;
  start_utc: string;
  end_utc: string;
  status: string;
  evaluation_points: number;
  valid_setups: number;
  no_trades: number;
  setup_wins: number;
  setup_losses: number;
  winrate: string | null;
  average_rr: string | null;
  max_drawdown_rr: string | null;
  created_at: string;
}

export interface LadderCell {
  label: string;
  sub_label: string;
  quarter_index: number;
  start_utc: string;
  end_utc: string;
  is_current: boolean;
}

export interface LadderRow {
  cycle: string;
  cells: LadderCell[];
}

export interface QuarterLadderResponse {
  as_of_utc: string;
  window_start_utc: string;
  window_end_utc: string;
  now_ratio: number;
  rows: LadderRow[];
}
