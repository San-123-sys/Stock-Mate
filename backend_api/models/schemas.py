from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "backend_api"


class ZerodhaStartResponse(BaseModel):
    login_url: str = Field(..., description="Kite login URL")
    state: str = Field(..., description="CSRF state token")


class ZerodhaCallbackResponse(BaseModel):
    success: bool
    message: str
    user_id: str | None = None
    account_id: str | None = None


class LinkedBrokerAccount(BaseModel):
    account_id: str | None = None
    scopes: str | None = None
    is_primary: bool = False
    updated_at: str | None = None


class ZerodhaStatusResponse(BaseModel):
    linked: bool
    provider: str = "zerodha"
    linked_accounts_count: int = 0
    accounts: list[LinkedBrokerAccount] = Field(default_factory=list)


class UpstoxStartResponse(BaseModel):
    login_url: str = Field(..., description="Upstox authorization URL")
    state: str = Field(..., description="CSRF state token")


class UpstoxStatusResponse(BaseModel):
    linked: bool
    provider: str = "upstox"
    linked_accounts_count: int = 0
    accounts: list[LinkedBrokerAccount] = Field(default_factory=list)


class ActionResponse(BaseModel):
    success: bool
    message: str


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=1)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    display_name: str | None = None


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    message: str = "Account created successfully"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = Field(default=None, description="Optional session override")
    response_mode: str | None = Field(default="quick", description="quick | explain")


class ChatResponse(BaseModel):
    user_id: str
    message: str
    answer: str
    action_tag: str = Field(..., description="Hold | Trim | Add | Watch | Rebalance | None")
    why: str = Field(..., description="One-sentence reasoning")
    risk_note: str = Field(default="", description="Risk caveat or disclaimer")
    confidence: str = Field(..., description="low | medium | high")
    detected_intent: str = Field(default="unknown", description="Detected user intent")
    confidence_score: float = Field(default=0.0, description="0.0 to 1.0 confidence score")
    next_steps: list[str] = Field(default_factory=list, description="Suggested follow-up prompts")
    proactive_insights: list[dict] = Field(default_factory=list, description="Proactive alerts and insights")
    portfolio_health: dict | None = Field(default=None, description="Portfolio health score breakdown")


class WatchlistAddRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, description="NSE/BSE ticker symbol")


class WatchlistResponse(BaseModel):
    user_id: str
    watchlist: list[str]
    count: int


class GoalSetRequest(BaseModel):
    target_amount: float = Field(..., gt=0, description="Target corpus in INR")
    years: float = Field(..., gt=0, description="Time horizon in years")
    label: str = Field(default="Financial Goal", description="Goal label")
    expected_return_pct: float = Field(default=12.0, description="Expected annualized return %")


class GoalResponse(BaseModel):
    user_id: str
    label: str
    target_amount: float
    current_amount: float
    years: float
    progress_pct: float
    monthly_sip_needed: float
    sip_note: str


class PortfolioSummaryResponse(BaseModel):
    user_id: str
    linked: bool
    account_id: str | None = None
    holdings_count: int = 0
    total_invested: float | None = None
    total_current_value: float | None = None
    total_pnl: float | None = None
    total_pnl_pct: float | None = None
    health_score: float | None = None
    portfolio_beta: float | None = None
    holdings: list[dict] = []
    data_status: str | None = None
    action_required: str | None = None
    link_endpoint: str | None = None
    message: str


class BenchmarkPoint(BaseModel):
    date: str
    portfolio_index: float
    nifty_index: float


class BenchmarkResponse(BaseModel):
    user_id: str
    linked: bool
    period: str
    data_status: str
    message: str
    action_required: str | None = None
    link_endpoint: str | None = None
    points: list[BenchmarkPoint] = []
    nifty_equivalent_value: float | None = None
    nifty_equivalent_diff: float | None = None


class SectorSlice(BaseModel):
    sector: str
    value: float
    pct: float


class SectorAllocationResponse(BaseModel):
    user_id: str
    linked: bool
    data_status: str
    message: str
    action_required: str | None = None
    link_endpoint: str | None = None
    slices: list[SectorSlice] = []
    over_concentrated: bool = False
    over_concentrated_sector: str | None = None
    over_concentrated_pct: float | None = None


class StockFundamentals(BaseModel):
    symbol: str
    long_name: str | None = None
    sector: str | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    dividend_yield: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    beta: float | None = None
    currency: str | None = None


class StockFinancialsResponse(BaseModel):
    linked: bool
    data_status: str
    message: str
    symbol: str
    action_required: str | None = None
    link_endpoint: str | None = None
    holding: dict | None = None
    fundamentals: StockFundamentals | None = None


class IndexSnapshot(BaseModel):
    symbol: str
    label: str
    price: float
    change: float
    change_pct: float


class HoldingMover(BaseModel):
    symbol: str
    change_pct: float
    current_value: float


class VixSnapshot(BaseModel):
    value: float
    sentiment: str


class MarketOverviewResponse(BaseModel):
    linked: bool
    data_status: str
    message: str
    indices: list[IndexSnapshot] = []
    top_gainers: list[HoldingMover] = []
    top_losers: list[HoldingMover] = []
    vix: VixSnapshot | None = None


class NewsArticle(BaseModel):
    title: str
    publisher: str | None = None
    link: str | None = None
    published_at: str | None = None
    sentiment_label: str | None = None
    sentiment_score: float | None = None


class SymbolNews(BaseModel):
    symbol: str
    articles: list[NewsArticle] = []


class NewsDigestResponse(BaseModel):
    linked: bool
    data_status: str
    message: str
    items: list[SymbolNews] = []


class ThemedBasket(BaseModel):
    theme: str
    description: str | None = None
    symbols: list[str] = []
    held_symbols: list[str] = []


class ThemedBasketsResponse(BaseModel):
    linked: bool
    data_status: str
    message: str
    baskets: list[ThemedBasket] = []


class PriceAlertCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    target_price: float = Field(..., gt=0)
    direction: Literal["above", "below"]


class PriceAlertResponse(BaseModel):
    id: int
    symbol: str
    target_price: float
    direction: str
    is_triggered: bool
    is_read: bool
    created_at: str | None = None
    triggered_at: str | None = None


class FrontierPoint(BaseModel):
    volatility: float
    ret: float
    sharpe: float


class PortfolioStats(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float


class OptimizedWeight(BaseModel):
    symbol: str
    current_pct: float
    target_pct: float


class RebalanceOrder(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL"]
    shares: int
    price: float
    est_value: float


class TaxLine(BaseModel):
    symbol: str
    shares: int
    realized_gain: float
    term: Literal["long", "short"]


class TaxImpact(BaseModel):
    estimated_tax: float
    realized_gain: float
    ltcg_gain: float
    stcg_gain: float
    ltcg_taxable_gain: float
    ltcg_exemption_inr: float = 125_000.0
    ltcg_rate_pct: float = 12.5
    stcg_rate_pct: float = 20.0
    note: str


class ProjectionPoint(BaseModel):
    month: int
    p5: float
    p50: float
    p95: float


class PortfolioProjection(BaseModel):
    points: list[ProjectionPoint] = []
    var_95_1d_pct: float
    cvar_95_1d_pct: float
    var_95_1d_value: float
    cvar_95_1d_value: float


class SignalView(BaseModel):
    symbol: str
    action_tag: str
    view_return_pct: float


class OptimizeResponse(BaseModel):
    user_id: str
    linked: bool = False
    objective: str
    data_status: str | None = None
    message: str
    action_required: str | None = None
    link_endpoint: str | None = None
    frontier: list[FrontierPoint] = []
    current_stats: PortfolioStats | None = None
    optimized_stats: PortfolioStats | None = None
    weights: list[OptimizedWeight] = []
    orders: list[RebalanceOrder] = []
    leftover_cash: float | None = None
    total_value: float | None = None
    note: str | None = None
    tax: TaxImpact | None = None
    tax_lines: list[TaxLine] = []
    projection_current: PortfolioProjection | None = None
    projection_optimized: PortfolioProjection | None = None
    views: list[SignalView] = []
