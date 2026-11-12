import { watch, onBeforeUnmount } from 'vue';
import { useTimerStore } from '../stores/timer';
import { useAuthStore } from '../stores/auth';
import { timerApi } from '../api';
import { clockNow } from '../utils/clock';
import { presenceDeviceId } from '../utils/presence';
export function useTimerOwnership() {
  const timer = useTimerStore(),
    auth = useAuthStore();
  let busy = false,
    alive = true,
    generation = 0;
  async function beat() {
    if (!auth.isLoggedIn || auth.isSuperAdmin || busy) return;
    busy = true;
    const uid = auth.user?.id,
      seq = generation;
    try {
      const c = timer.current;
      if (c && !timer.leaseLost && !c.leaseLost) {
        c.deviceId ||= presenceDeviceId();
        const body = {
          session_id: c.id,
          device_id: c.deviceId,
          started_at: Math.trunc(c.startedAt),
          label: c.learningContent || '',
        };
        try {
          await timerApi.heartbeat(body);
        } catch (e) {
          if (!e.status) throw e;
          if (e.status === 409) {
            try {
              await timerApi.start(body);
            } catch (claim) {
              if (
                alive &&
                seq === generation &&
                uid === auth.user?.id &&
                claim.status === 409 &&
                timer.current?.id === c.id
              ) {
                timer.leaseLost = true;
                c.leaseLost = true;
                if (!c.paused) {
                  c.paused = true;
                  c.pausedAt = Math.trunc(clockNow());
                }
                timer.saveCurrent();
              }
            }
          }
        }
      }
      const remote = await timerApi.current();
      if (alive && seq === generation && uid === auth.user?.id) timer.remoteLease = remote;
    } catch {
    } finally {
      busy = false;
    }
  }
  watch(
    () => auth.user?.id,
    () => {
      generation++;
      timer.remoteLease = null;
      timer.leaseLost = !!timer.current?.leaseLost;
      beat();
    },
    { immediate: true },
  );
  watch(
    () => timer.current?.id,
    () => {
      generation++;
      beat();
    },
  );
  const interval = setInterval(beat, 30000);
  window.addEventListener('online', beat);
  onBeforeUnmount(() => {
    alive = false;
    generation++;
    clearInterval(interval);
    window.removeEventListener('online', beat);
  });
}
