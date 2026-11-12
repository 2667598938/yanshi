// 账号切换：切换独立本地库 → 重新载入各 store → 启动/停止同步
import { activateAccount, initDb, db } from '../db';

export async function afterLogin(userId) {
  const { useAuthStore } = await import('../stores/auth');
  const adminOnly = useAuthStore().isSuperAdmin;
  const { useSchoolsStore } = await import('../stores/schools');
  useSchoolsStore().resetForAccount();
  await activateAccount(userId, { migrateGuest: !adminOnly });
  if (adminOnly) {
    const { useTimerStore } = await import('../stores/timer');
    useTimerStore().resetForAccount();
    const { resetSyncRuntime } = await import('./engine');
    resetSyncRuntime();
    return;
  }
  await initDb();
  await reloadLocal();
  const { initSyncForUser, resetSyncRuntime } = await import('./engine');
  resetSyncRuntime();
  await initSyncForUser();
}

export async function afterLogout() {
  const { useSchoolsStore } = await import('../stores/schools');
  useSchoolsStore().resetForAccount();
  await activateAccount(null);
  await initDb();
  await reloadLocal();
  const { resetSyncRuntime } = await import('./engine');
  resetSyncRuntime();
}

async function reloadLocal() {
  const [s, t, k, m] = await Promise.all([
    import('../stores/subjects'),
    import('../stores/timer'),
    import('../stores/tasks'),
    import('../stores/mistakes'),
  ]);
  const ss = s.useSubjectsStore();
  ss.list = await db.subjects.toArray();
  ss.loaded = true;

  const tm = t.useTimerStore();
  tm.resetForAccount();
  tm.sessions = await db.sessions.toArray();
  tm.loaded = true;

  const tk = k.useTasksStore();
  tk.list = await db.tasks.toArray();
  tk.loaded = true;

  const ms = m.useMistakesStore();
  await ms.load(true);
  const { useLearningSettingsStore } = await import('../stores/learningSettings');
  await useLearningSettingsStore().load(true);
  const { useProfileStore } = await import('../stores/profile');
  await useProfileStore().load(true);
  const { useTimeNodesStore } = await import('../stores/timeNodes');
  useTimeNodesStore().$reset();
  await useTimeNodesStore().load(true);
}
