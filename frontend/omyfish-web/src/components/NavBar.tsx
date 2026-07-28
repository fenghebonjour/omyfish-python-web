"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearTokens, getRefreshToken, getUserEmail, isLoggedIn } from "@/lib/auth";
import { refreshSession } from "@/lib/api";

export function NavBar() {
  const router = useRouter();
  const pathname = usePathname();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (isLoggedIn()) {
      setEmail(getUserEmail());
      return;
    }
    // Access token missing/expired — try a silent refresh before logging out.
    if (getRefreshToken()) {
      refreshSession().then((ok) => setEmail(ok ? getUserEmail() : null));
    } else {
      setEmail(null);
    }
  }, [pathname]);

  function logout() {
    clearTokens();
    setEmail(null);
    router.push("/login");
  }

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link href="/" className="text-blue-600 font-bold text-lg">OMyFish</Link>
        <Link href="/timing" className="text-sm text-gray-600 hover:text-gray-900">Timing</Link>
        <Link href="/" className="text-sm text-gray-600 hover:text-gray-900">Identify</Link>
        {email && (
          <>
            <Link href="/observations" className="text-sm text-gray-600 hover:text-gray-900">Observations</Link>
            <Link href="/notifications" className="text-sm text-gray-600 hover:text-gray-900">Notifications</Link>
          </>
        )}
      </div>
      <div className="flex items-center gap-4">
        {email ? (
          <>
            <span className="text-sm text-gray-500">{email}</span>
            <button onClick={logout} className="text-sm text-red-500 hover:text-red-700">Logout</button>
          </>
        ) : (
          <Link href="/login" className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700">
            Login
          </Link>
        )}
      </div>
    </nav>
  );
}
