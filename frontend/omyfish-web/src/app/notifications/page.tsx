"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getNotifications, markNotificationRead, type Notification } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    getNotifications()
      .then(setNotifications)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [router]);

  async function handleRead(id: string) {
    try {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true } : n))
      );
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-400 animate-pulse">Loading notifications...</p>
      </main>
    );
  }

  const unread = notifications.filter((n) => !n.read).length;

  return (
    <main className="min-h-screen bg-gray-50 py-10">
      <div className="max-w-2xl mx-auto px-4 flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
          {unread > 0 && <p className="text-sm text-blue-600 mt-1">{unread} unread</p>}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{error}</div>
        )}

        {notifications.length === 0 && !error ? (
          <div className="text-center py-20 text-gray-400">No notifications yet</div>
        ) : (
          <div className="flex flex-col gap-2">
            {notifications.map((n) => (
              <div
                key={n.id}
                className={`bg-white border rounded-xl p-4 flex justify-between items-start gap-4 shadow-sm ${
                  n.read ? "border-gray-200 opacity-70" : "border-blue-200"
                }`}
              >
                <div>
                  <p className={`font-medium text-gray-900 text-sm ${!n.read ? "font-semibold" : ""}`}>
                    {n.title}
                  </p>
                  {n.body && <p className="text-sm text-gray-500 mt-0.5">{n.body}</p>}
                  <p className="text-xs text-gray-400 mt-1">{new Date(n.createdAt).toLocaleString()}</p>
                </div>
                {!n.read && (
                  <button
                    onClick={() => handleRead(n.id)}
                    className="text-xs text-blue-600 hover:text-blue-800 shrink-0"
                  >
                    Mark read
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
