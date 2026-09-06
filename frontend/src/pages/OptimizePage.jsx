import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Scale, TriangleAlert, ArrowUpRight, ArrowDownRight, Link2, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { portfolio } from "../services/api";

const ease = [0.25, 0.1, 0.25, 1];
const pct = (x) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);
const inr = (x) => `₹${Math.round(x).toLocaleString("en-IN")}`;

function Shimmer({ className = "" }) {
  return (
    <div
      className={`animate-shimmer rounded-2xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)] ${className}`}
    />
  );
}

const OBJECTIVES = [
  { key: "min_vol", label: "Min Risk" },
  { key: "max_sharpe", label: "Max Sharpe" },
  { key: "black_litterman", label: "Signal-driven" },
];

function StatBlock({ title, stats, projection, accent }) {
  return (
    <div className="flex-1 rounded-2xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-overlay)] p-5">
      <p className="text-[11px] font-bold uppercase tracking-[2px] text-[var(--color-text-muted)] mb-4">{title}</p>
      <dl className="space-y-3">
        {[
          ["Expected return", pct(stats?.expected_return)],
          ["Volatility", pct(stats?.volatility)],
          ["Sharpe", stats?.sharpe == null ? "—" : stats.sharpe.toFixed(2)],
          ["1-day VaR (95%)", projection ? `${projection.var_95_1d_pct.toFixed(1)}%` : "—"],
          ["1-day CVaR (95%)", projection ? `${projection.cvar_95_1d_pct.toFixed(1)}%` : "—"],
        ].map(([k, v]) => (
          <div key={k} className="flex items-center justify-between">
            <dt className="text-xs text-[var(--color-text-secondary)]">{k}</dt>
            <dd className={`text-sm font-semibold tabular-nums ${accent ? "text-[var(--color-brand)]" : "text-[var(--color-text-primary)]"}`}>
              {v}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function FrontierChart({ frontier, current, optimized }) {
  const curve = frontier.map((p) => ({ x: p.volatility, y: p.ret }));
  const cur = current ? [{ x: current.volatility, y: current.expected_return }] : [];
  const opt = optimized ? [{ x: optimized.volatility, y: optimized.expected_return }] : [];
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <CartesianGrid stroke="var(--color-border-subtle)" />
          <XAxis
            type="number"
            dataKey="x"
            name="Volatility"
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="Return"
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
            tickLine={false}
            axisLine={false}
          />
          <ZAxis range={[60, 61]} />
          <Tooltip
            formatter={(v) => `${(v * 100).toFixed(1)}%`}
            contentStyle={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 12,
              fontSize: 12,
            }}
          />
          <Scatter name="Efficient frontier" data={curve} fill="var(--color-text-muted)" line shape="circle" />
          <Scatter name="Your portfolio" data={cur} fill="#EF4444" shape="cross" />
          <Scatter name="Optimized" data={opt} fill="var(--color-brand)" shape="star" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function ProjectionChart({ current, optimized, startValue }) {
  const data = optimized.points.map((p, i) => ({
    month: p.month,
    optP5: p.p5,
    optBand: p.p95 - p.p5,
    optP50: p.p50,
    curP50: current.points[i]?.p50 ?? null,
  }));
  data.unshift({ month: 0, optP5: startValue, optBand: 0, optP50: startValue, curP50: startValue });
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid stroke="var(--color-border-subtle)" />
          <XAxis
            dataKey="month"
            tickFormatter={(m) => (m === 0 ? "now" : `${m}m`)}
            tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
            tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
            tickLine={false}
            axisLine={false}
            width={52}
          />
          <Tooltip
            formatter={(v) => inr(v)}
            labelFormatter={(m) => (m === 0 ? "Today" : `Month ${m}`)}
            contentStyle={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 12,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Area type="monotone" dataKey="optP5" stackId="band" stroke="none" fill="transparent" name="5th pct" legendType="none" />
          <Area type="monotone" dataKey="optBand" stackId="band" stroke="none" fill="var(--color-brand)" fillOpacity={0.15} name="Optimized 5–95%" />
          <Line type="monotone" dataKey="optP50" stroke="var(--color-brand)" strokeWidth={2.5} dot={false} name="Optimized median" />
          <Line type="monotone" dataKey="curP50" stroke="#94A3B8" strokeWidth={2} strokeDasharray="4 4" dot={false} name="Current median" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function WeightsTable({ weights }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wider text-[var(--color-text-muted)] text-left">
            <th className="py-2 pr-4 font-semibold">Stock</th>
            <th className="py-2 px-4 font-semibold text-right">Current</th>
            <th className="py-2 px-4 font-semibold text-right">Target</th>
            <th className="py-2 pl-4 font-semibold text-right">Change</th>
          </tr>
        </thead>
        <tbody>
          {weights.map((w) => {
            const delta = w.target_pct - w.current_pct;
            return (
              <tr key={w.symbol} className="border-t border-[var(--color-border-subtle)]">
                <td className="py-2.5 pr-4 font-medium text-[var(--color-text-primary)]">{w.symbol}</td>
                <td className="py-2.5 px-4 text-right tabular-nums text-[var(--color-text-secondary)]">{w.current_pct.toFixed(1)}%</td>
                <td className="py-2.5 px-4 text-right tabular-nums text-[var(--color-text-primary)]">{w.target_pct.toFixed(1)}%</td>
                <td className={`py-2.5 pl-4 text-right tabular-nums ${delta > 0.05 ? "text-[var(--color-brand)]" : delta < -0.05 ? "text-[var(--color-loss)]" : "text-[var(--color-text-muted)]"}`}>
                  {delta > 0 ? "+" : ""}
                  {delta.toFixed(1)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function OrdersTable({ orders }) {
  if (!orders.length) {
    return <p className="text-sm text-[var(--color-text-secondary)]">Your portfolio already matches the target — no trades needed.</p>;
  }
  return (
    <div className="space-y-2">
      {orders.map((o) => (
        <div
          key={`${o.action}-${o.symbol}`}
          className="flex items-center justify-between px-4 py-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-overlay)]"
        >
          <div className="flex items-center gap-3">
            <span
              className={`flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                o.action === "BUY"
                  ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/30"
                  : "bg-rose-500/15 text-rose-500 border-rose-500/30"
              }`}
            >
              {o.action === "BUY" ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
              {o.action}
            </span>
            <span className="font-medium text-[var(--color-text-primary)]">{o.symbol}</span>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold text-[var(--color-text-primary)] tabular-nums">
              {o.shares} {o.shares === 1 ? "share" : "shares"}
            </p>
            <p className="text-xs text-[var(--color-text-muted)] tabular-nums">
              ≈ {inr(o.est_value)} @ ₹{o.price.toLocaleString("en-IN")}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function TaxCard({ tax, lines, shortTerm, onToggle }) {
  if (!tax || !lines.length) {
    return <p className="text-sm text-[var(--color-text-secondary)]">No sell orders — no capital-gains event.</p>;
  }
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-[var(--color-text-secondary)]">Estimated tax on these sells</span>
        <span className="text-lg font-semibold text-[var(--color-text-primary)] tabular-nums">{inr(tax.estimated_tax)}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-[var(--color-text-muted)]">
        <span>LTCG gain: {inr(tax.ltcg_gain)}</span>
        <span>STCG gain: {inr(tax.stcg_gain)}</span>
        <span>Taxable LTCG: {inr(tax.ltcg_taxable_gain)}</span>
        <span>Exemption: {inr(tax.ltcg_exemption_inr)}/yr</span>
      </div>
      <div className="space-y-1.5">
        {lines.map((ln) => (
          <label
            key={ln.symbol}
            className="flex items-center justify-between px-3 py-2 rounded-lg border border-[var(--color-border-subtle)] cursor-pointer"
          >
            <span className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={shortTerm.includes(ln.symbol)}
                onChange={() => onToggle(ln.symbol)}
                className="accent-[var(--color-brand)]"
              />
              <span className="font-medium text-[var(--color-text-primary)]">{ln.symbol}</span>
              <span className="text-[var(--color-text-muted)]">held ≤ 1 yr</span>
            </span>
            <span className={`text-xs tabular-nums ${ln.realized_gain >= 0 ? "text-[var(--color-brand)]" : "text-[var(--color-loss)]"}`}>
              {ln.realized_gain >= 0 ? "+" : ""}
              {inr(ln.realized_gain)} · {ln.term === "short" ? "STCG" : "LTCG"}
            </span>
          </label>
        ))}
      </div>
      <p className="text-[11px] text-[var(--color-text-muted)] leading-relaxed">{tax.note}</p>
    </div>
  );
}

function ViewsCard({ views }) {
  return (
    <div className="flex flex-wrap gap-2">
      {views.map((v) => (
        <span
          key={v.symbol}
          className={`text-xs px-2.5 py-1 rounded-full border ${
            v.action_tag === "Add"
              ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/30"
              : v.action_tag === "Trim"
              ? "bg-rose-500/15 text-rose-500 border-rose-500/30"
              : "bg-amber-500/15 text-amber-500 border-amber-500/30"
          }`}
        >
          {v.symbol} · {v.action_tag} · view {v.view_return_pct.toFixed(1)}%
        </span>
      ))}
    </div>
  );
}

export default function OptimizePage() {
  const [objective, setObjective] = useState("min_vol");
  const [shortTerm, setShortTerm] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    portfolio
      .optimize(objective, shortTerm)
      .then((res) => !cancelled && setData(res))
      .catch(() => !cancelled && setData(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [objective, shortTerm]);

  useEffect(load, [load]);

  const toggleShortTerm = (symbol) =>
    setShortTerm((prev) => (prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol]));

  const isLive = data?.data_status === "live";
  const notLinked = data?.action_required === "link_broker" || data?.action_required === "relink_broker";

  return (
    <div className="p-6 md:p-12 max-w-[1400px] mx-auto space-y-8 min-h-full">
      <div>
        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl md:text-5xl font-display leading-[1.1] text-[var(--color-text-primary)]"
        >
          <span className="italic font-normal">Portfolio</span>{" "}
          <span className="font-light tracking-tight">optimizer</span>
        </motion.h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-3 font-light tracking-wide uppercase">
          Efficient frontier, rebalance orders & tax impact for your live holdings
        </p>
      </div>

      <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3">
        <TriangleAlert size={16} className="text-amber-500 mt-0.5 shrink-0" />
        <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
          Estimates from 3 years of historical prices — <strong>not investment advice</strong>. Expected-return
          estimates are noisy; <strong>Min Risk</strong> is the robust default. Signal-driven blends the assistant's
          Add/Trim views via Black-Litterman. Tax is an estimate — holdings are assumed long-term unless you flag them.
        </p>
      </div>

      <div className="inline-flex rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-overlay)] p-1">
        {OBJECTIVES.map((o) => (
          <button
            key={o.key}
            onClick={() => setObjective(o.key)}
            className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${
              objective === o.key
                ? "bg-[var(--color-brand)] text-white"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-6">
          <Shimmer className="h-40" />
          <Shimmer className="h-72" />
        </div>
      ) : notLinked ? (
        <div className="glass-card p-16 flex flex-col items-center text-center gap-6">
          <div className="p-6 rounded-3xl bg-[var(--color-surface-overlay)] border border-[var(--color-border)]">
            <Link2 size={36} className="text-[var(--color-text-muted)]" />
          </div>
          <p className="text-base text-[var(--color-text-secondary)] max-w-md font-light leading-relaxed">
            {data?.message || "Link a broker to optimize your portfolio."}
          </p>
          <Link to="/broker" className="px-5 py-2.5 rounded-xl bg-[var(--color-brand)] text-white text-sm font-medium">
            Connect broker
          </Link>
        </div>
      ) : !isLive ? (
        <div className="glass-card p-16 flex flex-col items-center text-center gap-6">
          <div className="p-6 rounded-3xl bg-[var(--color-surface-overlay)] border border-[var(--color-border)]">
            <Scale size={36} className="text-[var(--color-text-muted)]" />
          </div>
          <p className="text-base text-[var(--color-text-secondary)] max-w-md font-light leading-relaxed">
            {data?.message || "Optimization is unavailable right now."}
          </p>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease }}
          className="space-y-6"
        >
          {data.note && (
            <p className="text-xs text-amber-500 bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-2">
              {data.note}
            </p>
          )}

          {objective === "black_litterman" && data.views?.length > 0 && (
            <div className="glass-card p-6 md:p-8">
              <h2 className="flex items-center gap-2 text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px] mb-5">
                <Sparkles size={14} /> Signal-driven views
              </h2>
              <ViewsCard views={data.views} />
            </div>
          )}

          <div className="glass-card p-6 md:p-8">
            <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px] mb-5">
              Current vs Optimized
            </h2>
            <div className="flex flex-col sm:flex-row gap-4">
              <StatBlock title="Your portfolio" stats={data.current_stats} projection={data.projection_current} />
              <StatBlock title="Optimized" stats={data.optimized_stats} projection={data.projection_optimized} accent />
            </div>
          </div>

          <div className="glass-card p-6 md:p-8">
            <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px] mb-5">
              Efficient frontier
            </h2>
            <FrontierChart frontier={data.frontier} current={data.current_stats} optimized={data.optimized_stats} />
          </div>

          {data.projection_optimized?.points?.length > 0 && (
            <div className="glass-card p-6 md:p-8">
              <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px] mb-5">
                12-month projection (Monte Carlo)
              </h2>
              <ProjectionChart
                current={data.projection_current}
                optimized={data.projection_optimized}
                startValue={data.total_value}
              />
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            <div className="glass-card p-6 md:p-8">
              <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px] mb-5">Target allocation</h2>
              <WeightsTable weights={data.weights} />
            </div>
            <div className="glass-card p-6 md:p-8">
              <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px] mb-5">Rebalance orders</h2>
              <OrdersTable orders={data.orders} />
              {data.leftover_cash != null && data.orders.length > 0 && (
                <p className="text-xs text-[var(--color-text-muted)] mt-4">
                  Est. uninvested after rebalance: {inr(data.leftover_cash)}
                </p>
              )}
            </div>
          </div>

          <div className="glass-card p-6 md:p-8">
            <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-[3px] mb-5">Tax impact</h2>
            <TaxCard tax={data.tax} lines={data.tax_lines} shortTerm={shortTerm} onToggle={toggleShortTerm} />
          </div>
        </motion.div>
      )}
    </div>
  );
}
