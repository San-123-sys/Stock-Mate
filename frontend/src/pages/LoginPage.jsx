import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import FoleoLogo from "../components/FoleoLogo";
import { useAuth } from "../context/AuthContext";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Loader2, Sparkles, CheckCircle2 } from "lucide-react";

const ease = [0.25, 0.1, 0.25, 1];

export default function LoginPage() {
  const { login, register, forgotPassword } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const [mode, setMode] = useState("login"); // "login" | "register" | "forgot"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [resetSent, setResetSent] = useState(false);

  const isRegister = mode === "register";
  const isForgot = mode === "forgot";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResetSent(false);

    if (isForgot) {
      if (!email.trim()) {
        setError("Email is required");
        return;
      }
      setSubmitting(true);
      try {
        await forgotPassword(email.trim());
        setResetSent(true);
      } catch (err) {
        setError(err.message || "Failed to send reset link.");
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (!email.trim() || !password.trim()) {
      setError("Email and password are required");
      return;
    }
    if (isRegister && password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }
    setSubmitting(true);
    try {
      if (isRegister) {
        await register({ email: email.trim(), password, displayName: displayName.trim() || undefined });
      } else {
        await login({ email: email.trim(), password });
      }
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || (isRegister ? "Registration failed" : "Login failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
      className="min-h-screen bg-[var(--color-surface)] flex flex-col relative overflow-hidden transition-colors duration-500"
    >
      {/* Ambient glow */}
      <div className="absolute top-[-20%] left-[50%] -translate-x-1/2 w-[600px] h-[600px] bg-[var(--color-brand)]/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[400px] h-[400px] bg-[var(--color-brand)]/5 rounded-full blur-[100px] pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center px-6 md:px-12 py-6">
        <Link to="/" className="flex items-center group block mt-2">
          <FoleoLogo size="lg" className="drop-shadow-sm group-hover:scale-[1.03] transition-transform" />
        </Link>
      </nav>

      {/* Form */}
      <div className="flex-1 flex items-center justify-center px-6 pb-20 relative z-10 mt-[-5vh]">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease }}
          className="w-full max-w-md"
        >
          <div className="text-center mb-10">
            <motion.h1
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1, ease }}
              className="text-4xl md:text-5xl font-display leading-[1.1] text-[var(--color-text-primary)]"
            >
              {isForgot ? (
                <><span className="italic font-normal">Reset</span>{" "}<span className="font-light tracking-tight text-[var(--color-text-primary)]/90">password</span></>
              ) : isRegister ? (
                <><span className="italic font-normal">Create</span>{" "}<span className="font-light tracking-tight text-[var(--color-text-primary)]/90">your account</span></>
              ) : (
                <><span className="italic font-normal">Welcome</span>{" "}<span className="font-light tracking-tight text-[var(--color-text-primary)]/90">back</span></>
              )}
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.25, ease }}
              className="mt-4 text-[var(--color-text-secondary)] text-base font-light"
            >
              {isForgot
                ? "Enter your email to receive a password reset link."
                : isRegister
                  ? "Sign up to start your AI-powered wealth journey."
                  : "Sign in to your Foleo account."}
            </motion.p>
          </div>

          {/* Mode toggle */}
          {!isForgot && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3, ease }}
              className="flex mb-8 rounded-2xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)] p-1.5 shadow-sm"
            >
              {["login", "register"].map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); setError(""); setResetSent(false); }}
                  className={`flex-1 py-3 text-[13px] font-semibold rounded-xl tracking-wide uppercase transition-all duration-300 ${mode === m
                      ? "bg-[var(--color-surface-raised)] text-[var(--color-text-primary)] shadow-sm border border-[var(--color-border)]"
                      : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
                    }`}
                >
                  {m === "login" ? "Sign In" : "Register"}
                </button>
              ))}
            </motion.div>
          )}

          <motion.form
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.35, ease }}
            onSubmit={handleSubmit}
            className="glass-card p-8 md:p-10 space-y-6 shadow-2xl relative"
          >
            <AnimatePresence mode="popLayout">
              {error && (
                <motion.div
                  key="error"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="px-5 py-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm font-medium shadow-sm"
                >
                  {error}
                </motion.div>
              )}
              {resetSent && (
                <motion.div
                  key="success"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-center gap-3 px-5 py-4 rounded-2xl bg-[var(--color-brand)]/10 border border-[var(--color-brand)]/20 text-[var(--color-brand)] text-sm font-medium shadow-sm"
                >
                  <CheckCircle2 size={18} />
                  Reset link sent to your email!
                </motion.div>
              )}
            </AnimatePresence>

            <div className="space-y-5">
              <div>
                <label className="block text-xs font-bold text-[var(--color-text-muted)] mb-2 tracking-widest uppercase">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full px-5 py-4 rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] text-[15px] focus:outline-none focus:border-[var(--color-brand)] focus:ring-4 focus:ring-[var(--color-brand)]/10 transition-all duration-300 shadow-sm font-light"
                  autoComplete="email"
                  autoFocus
                />
              </div>

              <AnimatePresence mode="popLayout">
                {isRegister && !isForgot && (
                  <motion.div
                    key="displayName"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <label className="block text-xs font-bold text-[var(--color-text-muted)] mb-2 tracking-widest uppercase">
                      Display Name <span className="text-[var(--color-text-muted)]/70 normal-case tracking-normal font-medium">(optional)</span>
                    </label>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="Your name"
                      className="w-full px-5 py-4 rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] text-[15px] focus:outline-none focus:border-[var(--color-brand)] focus:ring-4 focus:ring-[var(--color-brand)]/10 transition-all duration-300 shadow-sm font-light"
                      autoComplete="name"
                    />
                  </motion.div>
                )}
              </AnimatePresence>

              <AnimatePresence mode="popLayout">
                {!isForgot && (
                  <motion.div
                    key="password"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <label className="block text-xs font-bold text-[var(--color-text-muted)] tracking-widest uppercase">
                        Password
                      </label>
                      {mode === "login" && (
                        <button
                          type="button"
                          onClick={() => { setMode("forgot"); setError(""); setResetSent(false); }}
                          className="text-xs font-semibold text-[var(--color-brand)] hover:text-[var(--color-brand-light)] transition-colors"
                        >
                          Forgot password?
                        </button>
                      )}
                    </div>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={isRegister ? "Min 6 characters" : "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"}
                      className="w-full px-5 py-4 rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] text-[15px] focus:outline-none focus:border-[var(--color-brand)] focus:ring-4 focus:ring-[var(--color-brand)]/10 transition-all duration-300 shadow-sm font-light"
                      autoComplete={isRegister ? "new-password" : "current-password"}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full flex items-center justify-center gap-2 px-6 py-4 rounded-2xl bg-[var(--color-brand)] text-white font-semibold text-[15px] hover:bg-[var(--color-brand-light)] hover:-translate-y-0.5 disabled:transform-none disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-300 shadow-xl shadow-[var(--color-brand)]/20 mt-8"
            >
              {submitting ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <>
                  {isForgot ? "SEND RESET LINK" : isRegister ? "CREATE ACCOUNT" : "SIGN IN"}
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            {isForgot && (
              <div className="pt-2 text-center">
                <button
                  type="button"
                  onClick={() => { setMode("login"); setError(""); setResetSent(false); }}
                  className="text-[13px] font-semibold text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors inline-block"
                >
                  ← Back to Login
                </button>
              </div>
            )}
          </motion.form>

          <p className="text-center mt-10 text-xs text-[var(--color-text-muted)] font-light tracking-wide uppercase">
            Not financial advice. For educational purposes only.
          </p>
        </motion.div>
      </div>
    </motion.div>
  );
}
