// 本地主库：IndexedDB（Dexie）。学习数据全部先落地本地，可离线使用；
// 后端上线后再通过 /sync 增量同步。设置与"当前这颗番茄"仍存 localStorage。
import Dexie from 'dexie';
import { DEFAULT_SUBJECTS } from '../data/subjects';

export const LEGACY_SESS_KEY = 'yanshi:sessions';
export const CUR_KEY = 'yanshi:current';
export const MIGRATE_FLAG = 'yanshi:db_migrated_v1';

export function uid(prefix = '') {
  return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export const db = new Proxy(
  {},
  {
    get(_, prop) {
      const value = currentDb[prop];
      return typeof value === 'function' ? value.bind(currentDb) : value;
    },
    set(_, prop, value) {
      currentDb[prop] = value;
      return true;
    },
    has(_, prop) {
      return prop in currentDb;
    },
  },
);

// 每个账号独立 IndexedDB，避免换号后把上一个账号的未同步记录重新入队
let currentDb = createDb('yanshi_db');
let accountId = null;
let switchesInFlight = 0;

function createDb(name) {
  const instance = new Dexie(name);

  instance.version(1).stores({
    // 科目：id 主键，order 排序，archived 归档
    subjects: 'id, archived, order',
    // 番茄记录：date 用于按天聚合，subjectId / activityType 用于筛选
    sessions: 'id, date, subjectId, startedAt, activityType',
    // 任务：done / dueDate / createdAt / subjectId
    tasks: 'id, done, dueDate, createdAt, subjectId',
    // 错题：nextReviewAt 复习到期，*tags 多标签索引
    mistakes: 'id, subjectId, nextReviewAt, createdAt, *tags',
    // 键值（头像等）
    kv: 'key',
  });

  // v0.3 同步：outbox 待发变更、syncMeta 同步状态（增量声明，不影响已有表）
  instance.version(2).stores({
    outbox: '++id, recordId, type, createdAt',
    syncMeta: 'key',
  });

  // v0.4 离线社区：本地待上传动态、待同步收藏状态
  instance.version(3).stores({
    localPosts: 'id, createdAt',
    localFavs: 'resourceId, updatedAt',
  });

  instance.version(4).stores({ timeNodes: 'id' });
  instance.version(5).stores({ imageCache: 'key, lastAccessedAt, size' });
  return instance;
}

// 当前账号的「进行中的番茄」存储键（未登录时用公用键）
export function currentKey() {
  return accountId ? `${CUR_KEY}:u${accountId}` : CUR_KEY;
}

async function migrateGuestData(guest, target) {
  const tables = [
    'subjects',
    'sessions',
    'tasks',
    'mistakes',
    'outbox',
    'localPosts',
    'localFavs',
    'kv',
    'timeNodes',
  ];
  const snapshots = await guest.transaction('r', tables, async () =>
    Promise.all(tables.map((table) => guest[table].toArray())),
  );
  const migrated = await target.transaction('rw', tables, async () => {
    for (const table of tables) {
      if (await target[table].count()) return false;
    }
    for (const [index, table] of tables.entries()) {
      if (snapshots[index].length) await target[table].bulkPut(snapshots[index]);
    }
    return true;
  });
  // 跨库无法共用事务：先完整提交目标库，再清理游客库，失败时保留源数据。
  if (migrated) {
    await guest.transaction('rw', tables, async () => {
      for (const table of tables) await guest[table].clear();
    });
  }
  return migrated;
}

// 登录/登出/启动时切换账号数据源；首次登录把游客数据迁移进该账号库
export async function activateAccount(userId, { migrateGuest = false } = {}) {
  const nextId = userId ? Number(userId) : null;
  if (nextId === accountId) {
    if (!currentDb.isOpen()) await currentDb.open();
    return;
  }
  switchesInFlight += 1;
  try {
    let next;
    let claimedGuest = false;
    if (nextId && migrateGuest && accountId === null) {
      const target = createDb(`yanshi_db_u${nextId}`);
      await target.open();
      try {
        claimedGuest = await migrateGuestData(currentDb, target);
      } catch (e) {
        target.close();
        throw e;
      }
      await currentDb.close();
      next = target;
    } else {
      await currentDb.close();
      next = createDb(nextId ? `yanshi_db_u${nextId}` : 'yanshi_db');
      await next.open();
    }
    currentDb = next;
    accountId = nextId;

    if (claimedGuest) {
      const guestCurrent = localStorage.getItem(CUR_KEY);
      const accountCurrent = localStorage.getItem(currentKey());
      if (guestCurrent && !accountCurrent) localStorage.setItem(currentKey(), guestCurrent);
      if (guestCurrent) localStorage.removeItem(CUR_KEY);
    }
  } finally {
    switchesInFlight -= 1;
  }
}

// Capture the actual account database, not just a numeric user ID (A→B→A is stale too).
export function localAccountScope() {
  const source = currentDb;
  return {
    db: source,
    isCurrent: () => source === currentDb && switchesInFlight === 0,
    assertCurrent() {
      if (source !== currentDb || switchesInFlight > 0)
        throw new Error('账号已切换，请在当前账号重新操作');
    },
  };
}

export function activeAccountId() {
  return accountId;
}

// 首次启动：写入默认科目
async function seedSubjects() {
  const count = await db.subjects.count();
  if (count === 0) {
    await db.subjects.bulkAdd(
      DEFAULT_SUBJECTS.map((s, i) => ({
        id: s.id,
        name: s.name,
        color: s.color,
        icon: s.icon,
        tags: [],
        order: i,
        archived: 0,
        builtin: 1,
        createdAt: Date.now(),
      })),
    );
  }
}

// 一次性迁移旧 localStorage 番茄记录
async function migrateLegacy() {
  if (localStorage.getItem(MIGRATE_FLAG)) return;
  try {
    const raw = localStorage.getItem(LEGACY_SESS_KEY);
    const old = raw ? JSON.parse(raw) : [];
    if (Array.isArray(old) && old.length) {
      const validIds = new Set((await db.subjects.toArray()).map((s) => s.id));
      const rows = old
        .filter((x) => x.status === 'done')
        .map((x) => ({
          id: String(x.id ?? uid('s')),
          subjectId: validIds.has(x.subject) ? x.subject : 'other',
          mode: 'timer',
          activityType: '',
          plannedMin: x.plannedMin ?? 25,
          actualSec: x.actualSec ?? 0,
          status: 'done',
          startedAt: x.startedAt ?? Date.now(),
          endedAt: x.endedAt ?? Date.now(),
          date: x.date,
          note: x.note || '',
          createdAt: x.endedAt ?? Date.now(),
        }));
      if (rows.length) await db.sessions.bulkPut(rows);
    }
  } catch (e) {
    console.warn('旧数据迁移失败', e);
  }
  localStorage.setItem(MIGRATE_FLAG, '1');
}

export async function initDb() {
  await seedSubjects();
  await migrateLegacy();
}
