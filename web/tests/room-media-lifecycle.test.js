// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils';
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import RoomMedia from '../src/components/RoomMedia.vue';
import { useAuthStore } from '../src/stores/auth';

let capture, sockets, tracks, wrapper;
class TestSocket {
  static OPEN = 1;
  constructor() {
    this.readyState = 0;
    sockets.push(this);
  }
  send = vi.fn();
  close = vi.fn(function () {
    this.readyState = 3;
  });
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  welcome() {
    this.onmessage?.({ data: JSON.stringify({ type: 'welcome', peers: [], iceServers: [] }) });
  }
}
beforeEach(() => {
  sockets = [];
  tracks = [
    { kind: 'audio', stop: vi.fn() },
    { kind: 'video', stop: vi.fn() },
  ];
  const stream = {
    getTracks: () => tracks,
    getAudioTracks: () => [tracks[0]],
    getVideoTracks: () => [tracks[1]],
  };
  capture = vi.fn().mockResolvedValue(stream);
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: capture } });
  vi.stubGlobal('WebSocket', TestSocket);
  vi.stubGlobal('location', { protocol: 'http:', host: 'localhost:27342' });
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, 'srcObject', 'set').mockImplementation(() => {});
  const auth = useAuthStore();
  auth.user = { id: 7 };
  auth.accessToken = 'local-test-token';
  wrapper = mount(RoomMedia, { props: { roomId: 4 } });
});
afterEach(() => {
  wrapper?.unmount();
  vi.restoreAllMocks();
});

it('拒绝摄像头权限后可以重试，也不会创建信令连接', async () => {
  capture.mockRejectedValueOnce(Object.assign(new Error(), { name: 'NotAllowedError' }));
  await wrapper.get('.btn-primary').trigger('click');
  await flushPromises();
  expect(wrapper.get('[role="alert"]').text()).toContain('未获得设备权限');
  expect(sockets).toHaveLength(0);
  expect(wrapper.get('.btn-primary').attributes('disabled')).toBeUndefined();
});

it('离开页面时停止设备并关闭连接', async () => {
  await wrapper.get('.btn-primary').trigger('click');
  await flushPromises();
  expect(sockets.length, wrapper.text()).toBe(1);
  sockets[0].open();
  sockets[0].welcome();
  await flushPromises();
  expect(wrapper.text()).toContain('关闭音视频');
  wrapper.unmount();
  wrapper = null;
  for (const track of tracks) expect(track.stop).toHaveBeenCalledOnce();
  expect(sockets[0].close).toHaveBeenCalledOnce();
});

it('等待设备授权时离开页面，稍后返回的设备立即关闭', async () => {
  let done;
  capture.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        done = resolve;
      }),
  );
  await wrapper.get('.btn-primary').trigger('click');
  await flushPromises();
  wrapper.unmount();
  wrapper = null;
  done({ getTracks: () => tracks });
  await flushPromises();
  for (const track of tracks) expect(track.stop).toHaveBeenCalledOnce();
  expect(sockets).toHaveLength(0);
});

it('旧连接延迟关闭不能终止重新开启的音视频', async () => {
  await wrapper.get('.btn-primary').trigger('click');
  await flushPromises();
  expect(sockets.length, wrapper.text()).toBe(1);
  const old = sockets[0],
    delayedClose = old.onclose;
  old.open();
  old.welcome();
  await flushPromises();
  await wrapper.get('.btn-danger').trigger('click');
  await wrapper.get('.btn-primary').trigger('click');
  await flushPromises();
  delayedClose();
  await flushPromises();
  expect(sockets[1].close).not.toHaveBeenCalled();
  expect(wrapper.text()).toContain('正在连接');
});
