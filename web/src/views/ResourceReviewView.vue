<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { adminApi, resourceApi } from '../api';
import { useToast } from '../composables/useToast';
const router = useRouter(),
  { toast } = useToast(),
  rows = ref([]),
  status = ref('pending'),
  busy = ref(false),
  next = ref(null),
  notes = ref({});
async function load(more = false) {
  busy.value = true;
  try {
    const data = await adminApi.resourceQueue(status.value, more ? next.value || 0 : 0);
    rows.value = more ? [...rows.value, ...data.items] : data.items;
    next.value = data.next;
  } catch (e) {
    toast(e.message);
  } finally {
    busy.value = false;
  }
}
async function review(row, action) {
  const note = (notes.value[row.id] || '').trim();
  if (action === 'reject' && !note) return toast('请填写驳回原因');
  busy.value = true;
  try {
    await adminApi.reviewResource(row.id, { action, expected_revision: row.revision, note });
    toast(action === 'approve' ? '已通过并公开' : '已驳回并通知作者');
    await load();
  } catch (e) {
    toast(e.message);
    if (e.status === 409) await load();
  } finally {
    busy.value = false;
  }
}
async function takedown(row) {
  const reason = (prompt('下架原因（必填，会通知作者）') || '').trim();
  if (!reason) return;
  busy.value = true;
  try {
    await resourceApi.remove(row.id, reason);
    toast('已下架并通知作者');
    await load();
  } catch (e) {
    toast(e.message);
  } finally {
    busy.value = false;
  }
}
onMounted(() => load());
</script>
<template>
  <div class="page">
    <button class="btn btn-outline" @click="router.back()">返回后台</button>
    <h2>资料审核</h2>
    <p>
      待审内容只用于审核。个人备注不会进入本页面；已批准资料编辑时保留旧版公开，待新版本批准后替换。
    </p>
    <select v-model="status" class="input" :disabled="busy" @change="load()">
      <option value="pending">待审核</option>
      <option value="approved">已通过</option>
      <option value="rejected">已驳回</option>
      <option value="all">全部</option>
    </select>
    <div v-for="row in rows" :key="row.id" class="card mt16">
      <strong>{{ row.title }}</strong>
      <p>
        作者ID {{ row.user_id }} · 版本 {{ row.revision }} · {{ row.review_status }}
        {{ row.has_published_version ? '（有已公开版本）' : '' }}
      </p>
      <p>{{ row.category }} · {{ row.intro }}</p>
      <a :href="row.url" target="_blank" rel="noopener noreferrer">{{ row.url }}</a>
      <p>提取码：{{ row.code || '无' }}</p>
      <p v-if="row.review_note">审核说明：{{ row.review_note }}</p>
      <template v-if="row.review_status === 'pending'">
        <textarea
          v-model="notes[row.id]"
          class="input"
          maxlength="500"
          placeholder="驳回必须填写原因"
        ></textarea
        ><button class="btn btn-primary" :disabled="busy" @click="review(row, 'approve')">
          通过并公开</button
        ><button class="btn btn-outline" :disabled="busy" @click="review(row, 'reject')">
          驳回
        </button></template
      ><button class="btn btn-outline" :disabled="busy" @click="takedown(row)">下架资料</button>
    </div>
    <p v-if="!rows.length">当前队列为空</p>
    <button v-if="next" class="btn btn-outline" :disabled="busy" @click="load(true)">
      加载更多
    </button>
  </div>
</template>
<style scoped>
p {
  font-size: 14px;
  line-height: 1.7;
}
a {
  overflow-wrap: anywhere;
}
button {
  margin: 5px;
}
</style>
