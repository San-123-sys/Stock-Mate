import { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  MessageCircle,
  Briefcase,
  Sparkles,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  Link2,
  CheckSquare,
  Square,
  X,
  BarChart3,
  BellPlus,
  Share2,
  Scale,
} from "lucide-react";
import html2canvas from "html2canvas";
import { portfolio, chat, alerts } from "../services/api";
import ReportCard from "../components/ReportCard";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";

const COLORS = ["#10B981", "#06B6D4", "#8B5CF6", "#F59E0B", "#EF4444", "#EC4899", "#6366F1", "#14B8A6"];

function formatCurrencyINR(val) {
  if (val == null) return "—";
  const n = Number(val);
  if (isNaN(n)) return "—";
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

const ease = [0.25, 0.1, 0.25, 1];

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } }
};
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease } }
};

function StatCard({ icon: Icon, label, value, sub, trend }) {
  const isPositive = trend === "up";
  return (
    <motion.div variants={itemVariants} className="glass-card glass-card-hover p-8 group">
      <div className="flex items-start justify-between mb-6">
        <div className="p-3 rounded-2xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)] shadow-sm group-hover:scale-110 transition-transform duration-300">
          <Icon size={20} className="text-[var(--color-text-secondary)] group-hover:text-[var(--color-text-primary)] transition-colors" strokeWidth={1.8} />
        </div>
        {trend && (
          <span className={`flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full ${isPositive ? "bg-[var(--color-profit)]/10 text-[var(--color-profit)]" : "bg-[var(--color-loss)]/10 text-[var(--color-loss)]"}`}>
            {isPositive ? <TrendingUp size={13} strokeWidth={2.5} /> : <TrendingDown size={13} strokeWidth={2.5} />}
            {sub}
          </span>
        )}
      </div>
      <p className="text-3xl font-display font-semibold text-[var(--color-text-primary)] tracking-tight">{value}</p>
      <p className="text-xs text-[var(--color-text-secondary)] mt-2 uppercase tracking-[1.5px] font-semibold">{label}</p>
    </motion.div>
  );
}

function HealthGauge({ score }) {
  const clampedScore = Math.max(0, Math.min(100, score || 0));
  const color =
    clampedScore >= 70 ? "var(--color-brand)" : clampedScore >= 40 ? "#F59E0B" : "var(--color-loss)";
  const circumference = 2 * Math.PI * 58;
  const offset = circumference - (clampedScore / 100) * circumference;

  return (
    <div className="relative w-40 h-40 mx-auto group">
      <svg viewBox="0 0 130 130" className="w-full h-full -rotate-90 drop-shadow-sm">
        <circle cx="65" cy="65" r="58" fill="none" stroke="var(--color-border)" strokeWidth="8" />
        <motion.circle
          cx="65" cy="65" r="58" fill="none"
          stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.5, ease: [0.25, 0.1, 0.25, 1] }}
          className="group-hover:opacity-80 transition-opacity"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-display font-semibold text-[var(--color-text-primary)] tracking-tight">{clampedScore}</span>
        <span className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-[3px] font-bold mt-1">Health</span>
      </div>
    </div>
  );
}

function BetaBadge({ beta }) {
  if (beta == null) return null;
  const label = beta < 0.8 ? "Conservative" : beta <= 1.2 ? "Market-aligned" : "Aggressive";
  const color = beta < 0.8 ? "var(--color-text-secondary)" : beta <= 1.2 ? "var(--color-brand)" : "#F59E0B";
  return (
    <span
      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-[1.5px]"
      style={{ color, backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)` }}
      title={`Weighted portfolio beta: ${beta.toFixed(2)}`}
    >
      β {beta.toFixed(2)} · {label}
    </span>
  );
}

function InsightCard({ insight, onAction }) {
  const actionLabel = insight.action || "Ask Foleo";
  return (
    <div className="flex items-start gap-4 p-5 rounded-2xl bg-[var(--color-surface-overlay)] border border-[var(--color-border)] hover:border-[var(--color-brand)]/30 hover:shadow-md transition-all duration-300">
      <div className="p-2 rounded-xl bg-[var(--color-brand)]/10 mt-1 shrink-0">
        <Sparkles size={16} className="text-[var(--color-brand)]" />
      </div>
      <div>
        <p className="text-[15px] text-[var(--color-text-primary)] leading-relaxed font-light">{insight.message || insight}</p>
        <button
          onClick={() => onAction(insight)}
          className="inline-flex mt-3 text-sm text-[var(--color-brand)] font-medium items-center gap-1 hover:gap-2 transition-all"
        >
          {actionLabel} <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

function OnboardingChecklist({ items, demoMode, onToggleDemo }) {
  const completed = items.filter((item) => item.done).length;
  return (
    <motion.div variants={itemVariants} className="glass-card p-6 md:p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-5">
        <div>
          <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px]">Getting Started</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mt-2">{completed}/{items.length} complete</p>
        </div>
        <button
          onClick={onToggleDemo}
          className={`px-4 py-2 rounded-full text-xs font-semibold border transition-all ${demoMode ? "bg-[var(--color-brand)] text-white border-[var(--color-brand)]" : "bg-[var(--color-surface-overlay)] text-[var(--color-text-secondary)] border-[var(--color-border)]"}`}
        >
          {demoMode ? "Demo Mode On" : "Enable Demo Mode"}
        </button>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <Link
            key={item.label}
            to={item.to}
            className={`flex items-center justify-between px-4 py-3 rounded-xl border bg-[var(--color-surface-overlay)] hover:border-[var(--color-brand)]/40 transition-all ${item.done ? "border-[var(--color-border)]" : "border-[var(--color-brand)]/35 animate-pulse"}`}
          >
            <span className="flex items-center gap-3 text-sm text-[var(--color-text-primary)]">
              {item.done ? <CheckSquare size={16} className="text-[var(--color-brand)]" /> : <Square size={16} className="text-[var(--color-text-muted)]" />}
              {item.label}
            </span>
            <span className="text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">Open</span>
          </Link>
        ))}
      </div>
    </motion.div>
  );
}

function OnboardingCompleteCard() {
  return (
    <motion.div
      variants={itemVariants}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-6 md:p-8 border border-[var(--color-brand)]/25 bg-[var(--color-brand)]/5"
    >
      <div className="flex items-center gap-3 mb-2">
        <CheckSquare size={18} className="text-[var(--color-brand)]" />
        <h2 className="text-sm font-bold uppercase tracking-[2px] text-[var(--color-brand)]">Onboarding Complete</h2>
      </div>
      <p className="text-[15px] text-[var(--color-text-primary)] leading-relaxed">
        You are fully set up. Your app is now running in full-power mode.
      </p>
    </motion.div>
  );
}

function OptimizeTeaser({ data }) {
  if (!data || data.data_status !== "live" || !data.optimized_stats || !data.current_stats) return null;
  const curSharpe = data.current_stats.sharpe;
  const optSharpe = data.optimized_stats.sharpe;
  const trades = (data.orders || []).length;
  if (optSharpe <= curSharpe + 0.05 && trades === 0) return null;
  return (
    <motion.div
      variants={itemVariants}
      className="glass-card p-6 md:p-8 border border-[var(--color-brand)]/25 bg-[var(--color-brand)]/5"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Scale size={16} className="text-[var(--color-brand)]" />
            <h2 className="text-xs font-bold uppercase tracking-[2px] text-[var(--color-brand)]">Portfolio can be optimized</h2>
          </div>
          <p className="text-[15px] text-[var(--color-text-primary)] leading-relaxed">
            Rebalancing toward the efficient frontier could lift your Sharpe from{" "}
            <strong>{curSharpe.toFixed(2)}</strong> to <strong>{optSharpe.toFixed(2)}</strong>
            {trades > 0 ? ` in ${trades} trade${trades === 1 ? "" : "s"}.` : "."}
          </p>
        </div>
        <Link
          to="/optimize"
          className="shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[var(--color-brand)] text-white text-sm font-medium"
        >
          Open optimizer <ArrowRight size={15} />
        </Link>
      </div>
    </motion.div>
  );
}

function NoBrokerState() {
  return (
    <motion.div variants={itemVariants} className="glass-card p-16 flex flex-col items-center text-center gap-6 shadow-xl">
      <div className="p-6 rounded-3xl bg-[var(--color-surface-overlay)] border border-[var(--color-border)] shadow-sm">
        <Link2 size={36} className="text-[var(--color-text-muted)]" />
      </div>
      <div>
        <h2 className="text-3xl font-display text-[var(--color-text-primary)] mb-4">
          <span className="italic font-normal">Connect</span>{" "}
          <span className="font-light text-[var(--color-text-primary)]/90">your broker</span>
        </h2>
        <p className="text-base text-[var(--color-text-secondary)] max-w-md font-light leading-relaxed mx-auto">
          Link your Zerodha account to see live portfolio data, P&amp;L, holdings, and AI-powered insights.
        </p>
      </div>
      <Link
        to="/broker"
        className="mt-4 flex items-center gap-2 px-8 py-4 rounded-full bg-[var(--color-text-primary)] text-[var(--color-surface)] font-semibold text-sm hover:scale-105 transition-transform shadow-xl hover:shadow-2xl"
      >
        <Link2 size={16} />
        Connect Broker
      </Link>
    </motion.div>
  );
}

function Shimmer({ className = "" }) {
  return <div className={`animate-shimmer rounded-2xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)] ${className}`} />;
}

function _to_float(v) {
  const n = parseFloat(v);
  return isNaN(n) ? 0 : n;
}

const BENCHMARK_PERIODS = ["1M", "3M", "6M", "1Y"];

function NiftyWhatIfCallout({ totalInvested, niftyEquivalent, niftyDiff }) {
  if (niftyEquivalent == null || niftyDiff == null || !totalInvested) return null;
  const better = niftyDiff > 0;
  return (
    <div className="mt-6 px-5 py-4 rounded-2xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)] border-l-4 border-l-[var(--color-brand)]">
      <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
        If you had invested <span className="font-semibold text-[var(--color-text-primary)]">{formatCurrencyINR(totalInvested)}</span> in NIFTY 50 over this period instead, you'd have{" "}
        <span className="font-semibold text-[var(--color-text-primary)]">{formatCurrencyINR(niftyEquivalent)}</span> today — that's{" "}
        <span className={`font-semibold ${better ? "text-[var(--color-profit)]" : "text-[var(--color-loss)]"}`}>
          {formatCurrencyINR(Math.abs(niftyDiff))} {better ? "more" : "less"}
        </span>{" "}than your current portfolio.
      </p>
    </div>
  );
}

function BenchmarkChart({ data, loading, period, onPeriodChange, dataStatus, totalInvested, niftyEquivalent, niftyDiff }) {
  return (
    <motion.div variants={itemVariants} className="glass-card p-8 md:p-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px]">Portfolio vs NIFTY 50</h2>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-2">Indexed to 100 at period start · based on current holdings</p>
        </div>
        <div className="flex items-center p-1 rounded-full bg-[var(--color-surface-overlay)] border border-[var(--color-border)] w-fit">
          {BENCHMARK_PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => onPeriodChange(p)}
              className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all ${period === p ? "bg-[var(--color-brand)] text-white" : "text-[var(--color-text-secondary)]"}`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <Shimmer className="h-72" />
      ) : data.length > 0 ? (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
              <Tooltip
                contentStyle={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "12px",
                  fontSize: "13px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Line type="monotone" dataKey="portfolio_index" name="Your Portfolio" stroke="var(--color-brand)" strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="nifty_index" name="NIFTY 50" stroke="#94A3B8" strokeWidth={2} dot={false} strokeDasharray="4 4" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-72 flex items-center justify-center text-center">
          <p className="text-sm text-[var(--color-text-muted)] max-w-sm">
            {dataStatus === "market_data_unavailable"
              ? "Market data is temporarily unavailable. Try again shortly."
              : "No benchmark data available yet."}
          </p>
        </div>
      )}
      <NiftyWhatIfCallout totalInvested={totalInvested} niftyEquivalent={niftyEquivalent} niftyDiff={niftyDiff} />
    </motion.div>
  );
}

function ConcentrationBanner({ sector, pct }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="flex items-center gap-4 px-6 py-5 rounded-2xl bg-amber-500/10 border border-amber-500/20 shadow-sm"
    >
      <AlertCircle size={20} className="text-amber-500 shrink-0" />
      <p className="text-[15px] text-amber-600 dark:text-amber-400 font-medium">
        You have {pct}% exposure to {sector} — consider diversifying.
      </p>
    </motion.div>
  );
}

function IndexStat({ index }) {
  const isPositive = index.change_pct >= 0;
  return (
    <div className="flex-1 p-5 rounded-2xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)]">
      <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-[2px]">{index.label}</p>
      <p className="text-2xl font-display font-semibold text-[var(--color-text-primary)] mt-2 tracking-tight">
        {index.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
      </p>
      <span className={`inline-flex items-center gap-1 mt-2 text-xs font-bold ${isPositive ? "text-[var(--color-profit)]" : "text-[var(--color-loss)]"}`}>
        {isPositive ? <TrendingUp size={12} strokeWidth={2.5} /> : <TrendingDown size={12} strokeWidth={2.5} />}
        {isPositive ? "+" : ""}{index.change_pct.toFixed(2)}%
      </span>
    </div>
  );
}

function MoverRow({ mover }) {
  const isPositive = mover.change_pct >= 0;
  return (
    <div className="flex items-center justify-between px-4 py-2.5 rounded-xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)]">
      <span className="text-[13px] font-semibold text-[var(--color-text-primary)]">{mover.symbol}</span>
      <span className={`text-[13px] font-bold ${isPositive ? "text-[var(--color-profit)]" : "text-[var(--color-loss)]"}`}>
        {isPositive ? "+" : ""}{mover.change_pct.toFixed(2)}%
      </span>
    </div>
  );
}

function VixGauge({ vix }) {
  if (!vix) return null;
  const clamped = Math.max(0, Math.min(40, vix.value));
  const pct = (clamped / 40) * 100;
  const color =
    vix.sentiment === "Extreme Greed" || vix.sentiment === "Greed"
      ? "var(--color-brand)"
      : vix.sentiment === "Neutral"
      ? "#F59E0B"
      : "var(--color-loss)";
  const circumference = 2 * Math.PI * 32;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="flex items-center gap-4 px-4 py-2.5 rounded-xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)]">
      <div className="relative w-16 h-16 shrink-0">
        <svg viewBox="0 0 76 76" className="w-full h-full -rotate-90">
          <circle cx="38" cy="38" r="32" fill="none" stroke="var(--color-border)" strokeWidth="6" />
          <motion.circle
            cx="38" cy="38" r="32" fill="none"
            stroke={color} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-display font-semibold text-[var(--color-text-primary)]">{vix.value.toFixed(1)}</span>
        </div>
      </div>
      <div>
        <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-[2px]">India VIX</p>
        <p className="text-sm font-semibold mt-0.5" style={{ color }}>{vix.sentiment}</p>
      </div>
    </div>
  );
}

function MarketOverviewWidget({ data, loading }) {
  const indices = data?.indices || [];
  const gainers = data?.top_gainers || [];
  const losers = data?.top_losers || [];
  const dataStatus = data?.data_status;
  const vix = data?.vix;

  return (
    <motion.div variants={itemVariants} className="glass-card p-8 md:p-10">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-[var(--color-brand)]/10">
            <BarChart3 size={16} className="text-[var(--color-brand)]" />
          </div>
          <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px]">Market Overview</h2>
        </div>
        <VixGauge vix={vix} />
      </div>

      {loading ? (
        <div className="grid sm:grid-cols-2 gap-4">
          <Shimmer className="h-24" />
          <Shimmer className="h-24" />
        </div>
      ) : indices.length > 0 ? (
        <div className="grid lg:grid-cols-4 gap-6">
          <div className="lg:col-span-2 flex flex-col sm:flex-row gap-4">
            {indices.map((idx) => <IndexStat key={idx.symbol} index={idx} />)}
          </div>
          <div>
            <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-[2px] mb-3">Top Gainers</p>
            <div className="space-y-2">
              {gainers.length > 0 ? gainers.map((m) => <MoverRow key={m.symbol} mover={m} />) : (
                <p className="text-xs text-[var(--color-text-muted)] py-2">No gainers to show</p>
              )}
            </div>
          </div>
          <div>
            <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-[2px] mb-3">Top Losers</p>
            <div className="space-y-2">
              {losers.length > 0 ? losers.map((m) => <MoverRow key={m.symbol} mover={m} />) : (
                <p className="text-xs text-[var(--color-text-muted)] py-2">No losers to show</p>
              )}
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-[var(--color-text-muted)] py-6 text-center">
          {dataStatus === "market_data_unavailable" ? "Market data is temporarily unavailable." : "No market data available yet."}
        </p>
      )}
    </motion.div>
  );
}

function SetAlertForm({ symbol, defaultPrice }) {
  const [direction, setDirection] = useState("above");
  const [targetPrice, setTargetPrice] = useState(defaultPrice ? String(defaultPrice) : "");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const handleSave = async () => {
    const price = Number(targetPrice);
    if (!price || price <= 0) {
      setFeedback({ type: "error", text: "Enter a valid target price." });
      return;
    }
    setSaving(true);
    setFeedback(null);
    try {
      await alerts.create({ symbol, target_price: price, direction });
      setFeedback({ type: "success", text: "Alert saved." });
    } catch (err) {
      setFeedback({ type: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-4 rounded-2xl bg-[var(--color-surface-overlay)] border border-[var(--color-border)] space-y-3">
      <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">
        <BellPlus size={14} /> Set Price Alert
      </div>
      <div className="flex items-center gap-2">
        <div className="flex rounded-xl overflow-hidden border border-[var(--color-border)] shrink-0">
          {["above", "below"].map((d) => (
            <button
              key={d}
              onClick={() => setDirection(d)}
              className={`px-3 py-2 text-xs font-semibold capitalize transition-colors ${
                direction === d
                  ? "bg-[var(--color-brand)] text-white"
                  : "bg-[var(--color-surface)] text-[var(--color-text-secondary)]"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
        <input
          type="number"
          value={targetPrice}
          onChange={(e) => setTargetPrice(e.target.value)}
          placeholder="Target price"
          className="flex-1 min-w-0 px-3 py-2 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-sm text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-brand)]"
        />
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded-xl bg-[var(--color-brand)] text-white text-xs font-semibold disabled:opacity-50 shrink-0"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
      {feedback && (
        <p className={`text-xs font-medium ${feedback.type === "error" ? "text-red-500" : "text-[var(--color-brand)]"}`}>
          {feedback.text}
        </p>
      )}
    </div>
  );
}

function StockFinancialsPanel({ symbol, data, loading, onClose }) {
  const f = data?.fundamentals;
  const holding = data?.holding;
  const dataStatus = data?.data_status;

  const formatCurrency = (val) => {
    if (val == null) return "—";
    const n = Number(val);
    if (isNaN(n)) return "—";
    return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  };

  const formatLarge = (val) => {
    if (val == null) return "—";
    const n = Number(val);
    if (isNaN(n)) return "—";
    if (n >= 1e12) return `₹${(n / 1e12).toFixed(2)}T`;
    if (n >= 1e9) return `₹${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`;
    return formatCurrency(n);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }}
        transition={{ duration: 0.3, ease }}
        onClick={(e) => e.stopPropagation()}
        className="glass-card w-full max-w-lg max-h-[85vh] overflow-y-auto p-8 md:p-10 relative"
      >
        <button
          onClick={onClose}
          className="absolute top-6 right-6 p-2 rounded-full bg-[var(--color-surface-overlay)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          <X size={16} />
        </button>

        <h2 className="text-2xl font-display font-semibold text-[var(--color-text-primary)]">{symbol}</h2>

        {!loading && (
          <div className="mt-5">
            <SetAlertForm symbol={symbol} defaultPrice={holding?.last_price} />
          </div>
        )}

        {loading ? (
          <div className="space-y-3 mt-6">
            {[...Array(4)].map((_, i) => <Shimmer key={i} className="h-12" />)}
          </div>
        ) : f ? (
          <div className="mt-6 space-y-6">
            {f.long_name && <p className="text-sm text-[var(--color-text-secondary)]">{f.long_name}</p>}

            {holding && (
              <div className="grid grid-cols-2 gap-3 p-4 rounded-2xl bg-[var(--color-brand)]/5 border border-[var(--color-brand)]/15">
                <div>
                  <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">Qty</p>
                  <p className="text-sm font-semibold text-[var(--color-text-primary)]">{holding.quantity}</p>
                </div>
                <div>
                  <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">Avg Price</p>
                  <p className="text-sm font-semibold text-[var(--color-text-primary)]">{formatCurrency(holding.average_price)}</p>
                </div>
                <div>
                  <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">LTP</p>
                  <p className="text-sm font-semibold text-[var(--color-text-primary)]">{formatCurrency(holding.last_price)}</p>
                </div>
                <div>
                  <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">P&L</p>
                  <p className="text-sm font-semibold text-[var(--color-text-primary)]">{formatCurrency(holding.pnl)}</p>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">Sector</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{f.sector || "—"}</p>
              </div>
              <div>
                <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">Market Cap</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{formatLarge(f.market_cap)}</p>
              </div>
              <div>
                <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">P/E (Trailing)</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{f.pe_ratio != null ? f.pe_ratio.toFixed(2) : "—"}</p>
              </div>
              <div>
                <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">P/E (Forward)</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{f.forward_pe != null ? f.forward_pe.toFixed(2) : "—"}</p>
              </div>
              <div>
                <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">Dividend Yield</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{f.dividend_yield != null ? `${(f.dividend_yield * 100).toFixed(2)}%` : "—"}</p>
              </div>
              <div>
                <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">Beta</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{f.beta != null ? f.beta.toFixed(2) : "—"}</p>
              </div>
              <div>
                <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">52W High</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{formatCurrency(f.fifty_two_week_high)}</p>
              </div>
              <div>
                <p className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">52W Low</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{formatCurrency(f.fifty_two_week_low)}</p>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-[var(--color-text-muted)] mt-8 text-center py-8">
            {dataStatus === "market_data_unavailable"
              ? "Fundamentals are temporarily unavailable for this stock."
              : "No fundamentals data available."}
          </p>
        )}
      </motion.div>
    </motion.div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [portfolioData, setPortfolioData] = useState(null);
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);
  const [insightsLoading, setInsightsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [demoMode, setDemoMode] = useState(() => localStorage.getItem("sm_demo_mode") === "1");

  const [benchmarkPeriod, setBenchmarkPeriod] = useState("1M");
  const [benchmarkData, setBenchmarkData] = useState([]);
  const [benchmarkStatus, setBenchmarkStatus] = useState(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(true);
  const [niftyEquivalent, setNiftyEquivalent] = useState(null);
  const [niftyDiff, setNiftyDiff] = useState(null);

  const [sectorData, setSectorData] = useState(null);
  const [sectorLoading, setSectorLoading] = useState(true);

  const [marketOverview, setMarketOverview] = useState(null);
  const [marketOverviewLoading, setMarketOverviewLoading] = useState(true);

  const [optimizeTeaser, setOptimizeTeaser] = useState(null);

  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [stockFinancials, setStockFinancials] = useState(null);
  const [stockFinancialsLoading, setStockFinancialsLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await portfolio.summary();
      setPortfolioData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchInsights = async () => {
    setInsightsLoading(true);
    try {
      const data = await chat.proactiveInsights();
      setInsights(data.insights || []);
    } catch {
      // non-critical
    } finally {
      setInsightsLoading(false);
    }
  };

  const fetchBenchmark = async (period) => {
    setBenchmarkLoading(true);
    try {
      const data = await portfolio.benchmark(period);
      setBenchmarkData(data.points || []);
      setBenchmarkStatus(data.data_status);
      setNiftyEquivalent(data.nifty_equivalent_value ?? null);
      setNiftyDiff(data.nifty_equivalent_diff ?? null);
    } catch {
      setBenchmarkData([]);
      setBenchmarkStatus("market_data_unavailable");
      setNiftyEquivalent(null);
      setNiftyDiff(null);
    } finally {
      setBenchmarkLoading(false);
    }
  };

  const fetchSectorAllocation = async () => {
    setSectorLoading(true);
    try {
      const data = await portfolio.sectorAllocation();
      setSectorData(data);
    } catch {
      setSectorData(null);
    } finally {
      setSectorLoading(false);
    }
  };

  const fetchMarketOverview = async () => {
    setMarketOverviewLoading(true);
    try {
      const data = await portfolio.marketOverview();
      setMarketOverview(data);
    } catch {
      setMarketOverview(null);
    } finally {
      setMarketOverviewLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    fetchInsights();
    fetchBenchmark(benchmarkPeriod);
    fetchSectorAllocation();
    fetchMarketOverview();
  }, []);

  // Lazy, non-blocking: only after live holdings are known and worth optimizing.
  useEffect(() => {
    if (portfolioData?.data_status !== "live") return;
    if ((portfolioData?.holdings?.length ?? 0) < 3) return;
    let cancelled = false;
    portfolio
      .optimize("min_vol")
      .then((res) => !cancelled && setOptimizeTeaser(res))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [portfolioData?.data_status, portfolioData?.holdings?.length]);

  const handleBenchmarkPeriodChange = (period) => {
    setBenchmarkPeriod(period);
    fetchBenchmark(period);
  };

  const handleSelectStock = async (symbol) => {
    setSelectedSymbol(symbol);
    setStockFinancialsLoading(true);
    try {
      const data = await portfolio.stockFinancials(symbol);
      setStockFinancials(data);
    } catch {
      setStockFinancials(null);
    } finally {
      setStockFinancialsLoading(false);
    }
  };

  const handleCloseStockPanel = () => {
    setSelectedSymbol(null);
    setStockFinancials(null);
  };

  const formatCurrency = (val) => {
    if (val == null) return "—";
    const n = Number(val);
    if (isNaN(n)) return "—";
    return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  };

  const formatPct = (val) => {
    if (val == null) return "";
    const n = Number(val);
    return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
  };

  const isLinked = portfolioData?.linked === true;
  const isLive = portfolioData?.data_status === "live";
  const needsRelink = portfolioData?.action_required === "relink_broker";
  const effectivePortfolioData = (!isLinked && demoMode)
    ? {
        ...portfolioData,
        linked: true,
        data_status: "demo",
        total_current_value: 428650,
        total_invested: 397200,
        total_pnl: 31450,
        total_pnl_pct: 7.92,
        health_score: 74,
        holdings: [
          { tradingsymbol: "TCS", exchange: "NSE", quantity: 18, average_price: 3560, last_price: 3840 },
          { tradingsymbol: "HDFCBANK", exchange: "NSE", quantity: 52, average_price: 1510, last_price: 1648 },
          { tradingsymbol: "RELIANCE", exchange: "NSE", quantity: 24, average_price: 2620, last_price: 2745 },
        ],
      }
    : portfolioData;
  const effectiveInsights = (!isLinked && demoMode)
    ? [
        { message: "Demo insight: One sector is slightly overweight. Trim slowly, not dramatically.", action: "Create rebalance plan" },
        { message: "Demo insight: SIP top-ups can improve risk-adjusted returns over 6-12 months.", action: "Build SIP plan" },
      ]
    : insights;

  const effectiveIsLinked = effectivePortfolioData?.linked === true;
  const effectiveNeedsRelink = effectivePortfolioData?.action_required === "relink_broker";
  const pnl = effectivePortfolioData?.total_pnl ?? 0;
  const pnlPct = effectivePortfolioData?.total_pnl_pct ?? 0;
  const totalValue = effectivePortfolioData?.total_current_value ?? 0;
  const holdings = effectivePortfolioData?.holdings || [];
  const healthScore = effectivePortfolioData?.health_score;

  const topPerformer = holdings.reduce((best, h) => {
    const qty = _to_float(h.quantity);
    const avgPrice = _to_float(h.average_price);
    const ltp = _to_float(h.last_price);
    const invested = qty * avgPrice;
    if (invested <= 0) return best;
    const hPnlPct = ((qty * ltp - invested) / invested) * 100;
    const symbol = h.tradingsymbol || h.symbol;
    if (!symbol) return best;
    if (!best || hPnlPct > best.pnlPct) return { symbol, pnlPct: hPnlPct };
    return best;
  }, null);

  const reportCardRef = useRef(null);
  const [sharingReport, setSharingReport] = useState(false);

  const handleShareReport = async () => {
    if (!reportCardRef.current) return;
    setSharingReport(true);
    try {
      const canvas = await html2canvas(reportCardRef.current, { backgroundColor: null, scale: 2 });
      const dataUrl = canvas.toDataURL("image/png");
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = "stock-mate-portfolio-report.png";
      link.click();
    } catch {
      // best-effort client-side export; silently ignore failures
    } finally {
      setSharingReport(false);
    }
  };

  const checklistItems = [
    { label: "Connect broker", to: "/broker", done: isLinked },
    { label: "Ask your first AI question", to: "/chat", done: localStorage.getItem("sm_onboarding_first_chat") === "1" },
    { label: "Set your first goal", to: "/chat", done: localStorage.getItem("sm_onboarding_goal_set") === "1" },
  ];
  const showOnboarding = !isLinked || checklistItems.some((item) => !item.done);
  const onboardingComplete = checklistItems.every((item) => item.done);

  const handleToggleDemo = () => {
    const next = !demoMode;
    setDemoMode(next);
    localStorage.setItem("sm_demo_mode", next ? "1" : "0");
  };

  const handleInsightAction = (insight) => {
    const prompt = insight.action
      ? `${insight.action}: ${insight.message || ""}`
      : `Help me act on this insight: ${insight.message || ""}`;
    navigate("/chat", { state: { prefill: prompt } });
  };

  const demoSectorSlices = [
    { sector: "Information Technology", value: 218800, pct: 51.06 },
    { sector: "Financial Services", value: 85696, pct: 20.0 },
    { sector: "Energy", value: 65916, pct: 15.38 },
    { sector: "Other", value: 58238, pct: 13.56 },
  ];
  const effectiveSectorData = (!isLinked && demoMode)
    ? { slices: demoSectorSlices, over_concentrated: true, over_concentrated_sector: "Information Technology", over_concentrated_pct: 51.06 }
    : sectorData;
  const pieData = (effectiveSectorData?.slices || []).map((s) => ({ name: s.sector, value: s.value }));

  const demoMarketOverview = {
    data_status: "live",
    indices: [
      { symbol: "^NSEI", label: "NIFTY 50", price: 24812.35, change: 118.4, change_pct: 0.48 },
      { symbol: "^BSESN", label: "SENSEX", price: 81456.2, change: -92.1, change_pct: -0.11 },
    ],
    top_gainers: [
      { symbol: "TCS", change_pct: 7.87, current_value: 69120 },
      { symbol: "RELIANCE", change_pct: 4.77, current_value: 65880 },
    ],
    top_losers: [],
  };
  const effectiveMarketOverview = (!isLinked && demoMode) ? demoMarketOverview : marketOverview;

  return (
    <div className="p-6 md:p-12 max-w-[1400px] mx-auto space-y-10 min-h-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6">
        <div>
          <motion.h1
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-4xl md:text-5xl font-display leading-[1.1] text-[var(--color-text-primary)]"
          >
            <span className="italic font-normal">Your</span>{" "}
            <span className="font-light tracking-tight">portfolio</span>
          </motion.h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-3 font-light tracking-wide uppercase">
            {isLive
              ? `Live Data · ACC: ${portfolioData.account_id}`
              : effectiveIsLinked
              ? `Broker linked · ${portfolioData?.data_status || 'syncing'}`
              : demoMode
              ? "Demo data · connect broker for live sync"
              : "Connect a broker to see live data"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {effectiveIsLinked && (
            <button
              onClick={handleShareReport}
              disabled={sharingReport}
              className="flex items-center gap-2 px-4 py-3 rounded-xl bg-[var(--color-surface-overlay)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-border-subtle)] transition-all duration-300 shadow-sm disabled:opacity-50"
              title="Share portfolio report"
            >
              <Share2 size={16} className={sharingReport ? "animate-pulse" : ""} />
              <span className="text-xs font-bold uppercase tracking-wider hidden sm:inline">Share</span>
            </button>
          )}
          <button
            onClick={() => { fetchData(); fetchInsights(); }}
            className="p-3 rounded-xl bg-[var(--color-surface-overlay)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-border-subtle)] transition-all duration-300 shadow-sm"
            title="Refresh Dashboard"
          >
            <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      <div style={{ position: "fixed", top: -9999, left: -9999, pointerEvents: "none" }}>
        <ReportCard
          ref={reportCardRef}
          healthScore={healthScore}
          pnlPct={pnlPct}
          topPerformer={topPerformer}
          sectorSlices={effectiveSectorData?.slices || []}
          generatedAt={new Date().toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
        />
      </div>

      {/* Errors / Warnings */}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex items-center gap-3 px-6 py-5 rounded-2xl bg-red-500/10 border border-red-500/20 shadow-sm">
            <AlertCircle size={20} className="text-red-500 shrink-0" />
            <p className="text-[15px] text-red-500 font-medium">{error}</p>
          </motion.div>
        )}
        {!loading && needsRelink && (
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex items-center justify-between px-6 py-5 rounded-2xl bg-amber-500/10 border border-amber-500/20 shadow-sm">
            <div className="flex items-center gap-4">
              <AlertCircle size={20} className="text-amber-500 shrink-0" />
              <p className="text-[15px] text-amber-600 dark:text-amber-400 font-medium">Session expired. Reconnect to see live data.</p>
            </div>
            <Link to="/broker" className="shrink-0 text-[13px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 hover:text-amber-700 underline">Reconnect</Link>
          </motion.div>
        )}
        {!loading && effectiveSectorData?.over_concentrated && (
          <ConcentrationBanner
            sector={effectiveSectorData.over_concentrated_sector}
            pct={effectiveSectorData.over_concentrated_pct}
          />
        )}
      </AnimatePresence>

      {loading ? (
        <div className="space-y-8">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => <Shimmer key={i} className="h-36" />)}
          </div>
          <div className="grid lg:grid-cols-2 gap-8">
            <Shimmer className="h-80" />
            <Shimmer className="h-80" />
          </div>
        </div>
      ) : !effectiveIsLinked && !effectiveNeedsRelink && !demoMode ? (
        <NoBrokerState />
      ) : (
        <motion.div variants={containerVariants} initial="hidden" animate="show" className="space-y-8">
          {showOnboarding && (
            <OnboardingChecklist items={checklistItems} demoMode={demoMode} onToggleDemo={handleToggleDemo} />
          )}
          {!showOnboarding && onboardingComplete && <OnboardingCompleteCard />}

          <OptimizeTeaser data={optimizeTeaser} />

          <MarketOverviewWidget data={effectiveMarketOverview} loading={marketOverviewLoading} />

          {/* Stats grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard icon={Briefcase} label="Current Value" value={formatCurrency(totalValue)} />
            <StatCard icon={pnl >= 0 ? TrendingUp : TrendingDown} label="Total P&L" value={formatCurrency(pnl)} sub={formatPct(pnlPct)} trend={pnl >= 0 ? "up" : "down"} />
            <StatCard icon={Activity} label="Holdings" value={holdings.length} />
            <StatCard icon={Activity} label="Invested" value={formatCurrency(portfolioData?.total_invested)} />
          </div>

          {/* Dash mid row */}
          <div className="grid lg:grid-cols-5 gap-6">
            {/* Health */}
            <motion.div variants={itemVariants} className="glass-card p-10 lg:col-span-2 flex flex-col items-center text-center justify-center relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-[var(--color-brand)]/5 rounded-full blur-[80px] -mr-32 -mt-32 pointer-events-none" />
              <div className="flex items-center justify-between w-full mb-8">
                <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px]">Portfolio Health</h2>
                <BetaBadge beta={effectivePortfolioData?.portfolio_beta} />
              </div>
              {healthScore != null ? (
                <>
                  <HealthGauge score={healthScore} />
                  <p className="text-sm text-[var(--color-text-secondary)] mt-8 leading-relaxed max-w-[250px]">
                    {healthScore >= 70 ? "Your portfolio is in great shape!" : healthScore >= 40 ? "Room for improvement — diversification may help." : "Consider rebalancing your portfolio."}
                  </p>
                </>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)] py-12">Health score unavailable</p>
              )}
            </motion.div>

            {/* Allocation */}
            <motion.div variants={itemVariants} className="glass-card p-10 lg:col-span-3 flex flex-col">
              <h2 className="text-xs font-bold text-[var(--color-text-muted)] mb-6 uppercase tracking-[3px]">Allocation</h2>
              {pieData.length > 0 ? (
                <div className="flex-1 flex flex-col sm:flex-row items-center gap-8">
                  <div className="w-full sm:w-1/2 h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={pieData} cx="50%" cy="50%" innerRadius={70} outerRadius={100} paddingAngle={4} dataKey="value" stroke="none">
                          {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="w-full sm:w-1/2 flex flex-col gap-4">
                    {pieData.map((d, i) => (
                      <div key={d.name} className="flex items-center justify-between p-3 rounded-xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)]">
                        <div className="flex items-center gap-3">
                          <div className="w-3.5 h-3.5 rounded-full shadow-sm" style={{ background: COLORS[i % COLORS.length] }} />
                          <span className="text-[13px] font-medium text-[var(--color-text-primary)]">{d.name}</span>
                        </div>
                        <span className="text-[13px] text-[var(--color-text-secondary)]">{formatCurrency(d.value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)] text-center m-auto py-12">No allocation data</p>
              )}
            </motion.div>
          </div>

          <BenchmarkChart
            data={benchmarkData}
            loading={benchmarkLoading}
            period={benchmarkPeriod}
            onPeriodChange={handleBenchmarkPeriodChange}
            dataStatus={benchmarkStatus}
            totalInvested={portfolioData?.total_invested}
            niftyEquivalent={niftyEquivalent}
            niftyDiff={niftyDiff}
          />

          {/* Holdings Table */}
          {holdings.length > 0 && (
            <motion.div variants={itemVariants} className="glass-card p-0 overflow-hidden">
              <div className="p-8 pb-6 border-b border-[var(--color-border-subtle)]">
                <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px]">Holdings ({holdings.length})</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[var(--color-surface-overlay)]/50">
                    <tr className="text-[11px] text-[var(--color-text-muted)] uppercase tracking-[2px]">
                      <th className="text-left font-bold px-8 py-5">Symbol</th>
                      <th className="text-left font-bold px-8 py-5">Broker</th>
                      <th className="text-right font-bold px-8 py-5">Qty</th>
                      <th className="text-right font-bold px-8 py-5">Avg Price</th>
                      <th className="text-right font-bold px-8 py-5">LTP</th>
                      <th className="text-right font-bold px-8 py-5">Current Value</th>
                      <th className="text-right font-bold px-8 py-5">P&L</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border-subtle)]">
                    {holdings.map((h, i) => {
                      const qty = _to_float(h.quantity);
                      const avgPrice = _to_float(h.average_price);
                      const ltp = _to_float(h.last_price);
                      const currentVal = qty * ltp;
                      const invested = qty * avgPrice;
                      const pnlVal = currentVal - invested;
                      const pnlPctVal = invested > 0 ? (pnlVal / invested) * 100 : 0;
                      const pos = pnlVal >= 0;
                      const symbol = h.tradingsymbol || h.symbol;
                      return (
                        <tr
                          key={i}
                          onClick={() => symbol && handleSelectStock(symbol)}
                          className={`hover:bg-[var(--color-surface-overlay)] transition-colors duration-200 group ${symbol ? "cursor-pointer" : ""}`}
                        >
                          <td className="px-8 py-5 font-semibold text-[var(--color-text-primary)]">
                            {h.tradingsymbol || h.symbol || "—"}
                            {h.exchange && <span className="ml-2 px-2 py-0.5 rounded text-[10px] bg-[var(--color-border)] text-[var(--color-text-secondary)] font-medium uppercase tracking-wider">{h.exchange}</span>}
                          </td>
                          <td className="px-8 py-5">
                            <span className="px-2 py-0.5 rounded-full text-[10px] bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)] font-semibold uppercase tracking-wider border border-[var(--color-border-subtle)]">
                              {h._source === "upstox" ? "Upstox" : "Zerodha"}
                            </span>
                          </td>
                          <td className="px-8 py-5 text-right text-[var(--color-text-secondary)] font-medium">{qty}</td>
                          <td className="px-8 py-5 text-right text-[var(--color-text-secondary)] font-medium">{formatCurrency(avgPrice)}</td>
                          <td className="px-8 py-5 text-right text-[var(--color-text-secondary)] font-medium">{formatCurrency(ltp)}</td>
                          <td className="px-8 py-5 text-right text-[var(--color-text-primary)] font-bold">{formatCurrency(currentVal)}</td>
                          <td className={`px-8 py-5 text-right font-bold ${pos ? "text-[var(--color-profit)]" : "text-[var(--color-loss)]"}`}>
                            {formatCurrency(pnlVal)}
                            <span className="block text-[11px] font-medium opacity-80 mt-1">{formatPct(pnlPctVal)}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}

          {/* Bottom section: Insights & Actions */}
          <div className="grid lg:grid-cols-3 gap-6">
            <motion.div variants={itemVariants} className="glass-card p-8 lg:col-span-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-[var(--color-brand)]/10">
                    <Sparkles size={16} className="text-[var(--color-brand)]" />
                  </div>
                  <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px]">AI Insights</h2>
                </div>
                <Link to="/chat" className="flex items-center justify-center gap-2 px-4 py-2 rounded-full border border-[var(--color-border)] text-[11px] font-bold tracking-widest uppercase text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-overlay)] transition-all">
                  Chat <ArrowRight size={13} />
                </Link>
              </div>
              
              {insightsLoading ? (
                <div className="space-y-4">
                  {[...Array(2)].map((_, i) => <Shimmer key={i} className="h-24" />)}
                </div>
              ) : effectiveInsights.length > 0 ? (
                <div className="space-y-4">
                  {effectiveInsights.map((ins, i) => (
                    <InsightCard key={i} insight={ins} onAction={handleInsightAction} />
                  ))}
                </div>
              ) : (
                <div className="py-12 flex flex-col items-center justify-center text-center border border-dashed border-[var(--color-border-subtle)] rounded-2xl">
                   <MessageCircle size={32} className="text-[var(--color-text-muted)]/50 mb-4" />
                   <p className="text-[15px] text-[var(--color-text-muted)] max-w-sm">No insights yet. Complete a portfolio sync and chat with Foleo AI to generate some.</p>
                </div>
              )}
            </motion.div>

            {/* Actions */}
            <motion.div variants={itemVariants} className="flex flex-col gap-6">
              {[
                { to: "/chat", icon: MessageCircle, title: "AI Assistant", desc: "Ask questions, get advice" },
                { to: "/broker", icon: Link2, title: "Broker Connections", desc: "Manage sync and permissions" },
              ].map((action) => (
                <Link key={action.to} to={action.to} className="flex-1 flex flex-col justify-center glass-card hover:border-[var(--color-brand)]/30 hover:scale-[1.02] transition-all p-8 group">
                  <div className="p-3.5 rounded-2xl bg-[var(--color-surface-overlay)] w-max mb-5 group-hover:bg-[var(--color-brand)]/10 group-hover:scale-110 transition-all shadow-sm">
                    <action.icon size={22} className="text-[var(--color-text-secondary)] group-hover:text-[var(--color-brand)] transition-colors" />
                  </div>
                  <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">{action.title}</h3>
                  <p className="text-[13px] text-[var(--color-text-secondary)]">{action.desc}</p>
                </Link>
              ))}
            </motion.div>
          </div>
        </motion.div>
      )}

      <AnimatePresence>
        {selectedSymbol && (
          <StockFinancialsPanel
            symbol={selectedSymbol}
            data={stockFinancials}
            loading={stockFinancialsLoading}
            onClose={handleCloseStockPanel}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

