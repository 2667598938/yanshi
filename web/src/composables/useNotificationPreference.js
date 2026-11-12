import { ref } from 'vue';
import { useAppStore } from '../stores/app';
import { useProfileStore } from '../stores/profile';
import { useToast } from './useToast';

export function useNotificationPreference() {
  const app = useAppStore();
  const profile = useProfileStore();
  const { toast } = useToast();
  const busy = ref(false);

  async function toggle() {
    if (busy.value) return;
    busy.value = true;
    const enabled = !app.notifyEnabled;
    try {
      // An account preference can be disabled even on a device without permission.
      if (enabled) {
        if (!('Notification' in window)) return toast('当前浏览器不支持通知');
        const permission =
          Notification.permission === 'granted'
            ? 'granted'
            : await Notification.requestPermission();
        if (permission !== 'granted') return toast('未获得通知权限');
      }
      await profile.save({ notify_enabled: enabled });
      app.setNotifyEnabled(enabled);
      toast(enabled ? '已开启到点通知' : '已关闭通知');
    } catch (e) {
      toast(e.message || '通知设置保存失败');
    } finally {
      busy.value = false;
    }
  }

  return { toggle, busy };
}
