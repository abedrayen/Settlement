"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { homePathForRole } from "@/lib/roles";
import { IconSparkle } from "@/components/icons";
import { Button } from "@/components/ui/Button";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await login(email.trim(), password);
      router.replace(homePathForRole(user.role));
    } catch {
      setError("Invalid email or password.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-slate-950">
      <div className="hidden lg:flex w-[46%] relative overflow-hidden flex-col justify-between p-12 text-white">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900" />
        <div className="absolute inset-0 opacity-40 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-500/30 via-transparent to-transparent" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center">
              <IconSparkle className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-lg font-semibold tracking-tight">Settlement AI</p>
              <p className="text-xs text-slate-400">Portfolio Intelligence</p>
            </div>
          </div>
        </div>
        <div className="relative max-w-md">
          <h1 className="text-4xl font-semibold tracking-tight leading-tight">
            Decision intelligence for settlement portfolios
          </h1>
        </div>
        <div />
      </div>

      <div className="flex-1 flex items-center justify-center p-6 bg-slate-100">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2.5 mb-6">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <IconSparkle className="w-4 h-4 text-white" />
            </div>
            <p className="text-sm font-semibold text-slate-900">Settlement AI</p>
          </div>

          <div className="card p-6 space-y-5">
            <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Sign in</h2>

            <form onSubmit={onSubmit} className="space-y-4">
              <label className="block space-y-1.5">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Email</span>
                <input
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field w-full"
                  required
                />
              </label>
              <label className="block space-y-1.5">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Password</span>
                <input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field w-full"
                  required
                />
              </label>
              {error && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-md px-3 py-2">{error}</p>
              )}
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
