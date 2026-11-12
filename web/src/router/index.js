import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { authorizeRoute } from './access';

export const routes = [
  { path: '/group/admission', redirect: '/rooms' },
  { path: '/admin/group', redirect: '/admin' },
  {
    path: '/group',
    component: () => import('../views/GroupLearningView.vue'),
    meta: { requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/schools/manage',
    component: () => import('../views/SchoolAdminView.vue'),
    meta: { requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/settings/time-nodes',
    component: () => import('../views/TimeNodesView.vue'),
    meta: { requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/admin/operations',
    component: () => import('../views/AdminOperationsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, hideTabbar: true },
  },
  {
    path: '/admin/resources',
    component: () => import('../views/ResourceReviewView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, hideTabbar: true },
  },
  {
    path: '/admin/schools',
    name: 'school-admin',
    component: () => import('../views/SchoolAdminView.vue'),
    meta: { title: '院校与校园图片', requiresAuth: true, requiresAdmin: true, hideTabbar: true },
  },
  {
    path: '/me/phone',
    name: 'phone-settings',
    component: () => import('../views/PhoneSettingsView.vue'),
    meta: { title: '绑定手机号', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { title: '今日' },
  },
  {
    path: '/stats',
    name: 'stats',
    component: () => import('../views/StatsView.vue'),
    meta: { title: '统计' },
  },
  {
    path: '/focus',
    name: 'focus',
    component: () => import('../views/FocusView.vue'),
    meta: { title: '专注' },
  },
  {
    path: '/room',
    name: 'room',
    component: () => import('../views/RoomView.vue'),
    meta: { title: '自习室', requiresAuth: true },
  },
  {
    path: '/rooms',
    name: 'rooms',
    component: () => import('../views/RoomsView.vue'),
    meta: { title: '自习室', requiresAuth: true },
  },
  {
    path: '/rooms/:id',
    name: 'room-detail',
    component: () => import('../views/RoomView.vue'),
    meta: { title: '自习室', requiresAuth: true },
  },
  {
    path: '/ai',
    name: 'ai',
    component: () => import('../views/AiView.vue'),
    meta: { title: 'AI', requiresAuth: true },
  },
  {
    path: '/me/:category(learning|content|account|group|data)',
    name: 'settings-category',
    component: () => import('../views/SettingsCategoryView.vue'),
    meta: { title: '我的设置', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/me',
    name: 'me',
    component: () => import('../views/MeView.vue'),
    meta: { title: '我的', requiresAuth: true },
  },

  // 会员 / 功能申请（隐藏底部导航）
  {
    path: '/vip',
    name: 'vip',
    component: () => import('../views/VipView.vue'),
    meta: { title: '会员中心', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/vip/redeem',
    name: 'vip-redeem',
    component: () => import('../views/VipRedeemView.vue'),
    meta: { title: '开通 VIP', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/requests',
    name: 'requests',
    component: () => import('../views/RequestsView.vue'),
    meta: { title: '功能申请', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/error-types',
    name: 'error-types',
    component: () => import('../views/ErrorTypesView.vue'),
    meta: { title: '错误类型', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/disclaimer',
    name: 'disclaimer',
    component: () => import('../views/DisclaimerView.vue'),
    meta: { title: '免责声明', hideTabbar: true },
  },
  {
    path: '/ai/settings',
    name: 'ai-settings',
    component: () => import('../views/AiSettingsView.vue'),
    meta: { title: 'AI 设置', requiresAuth: true, hideTabbar: true },
  },

  // 消息 / 资料区
  {
    path: '/messages',
    name: 'messages',
    component: () => import('../views/MessagesView.vue'),
    meta: { title: '消息中心', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/resources',
    name: 'resources',
    component: () => import('../views/ResourcesView.vue'),
    meta: { title: '资料库', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/resources/edit',
    name: 'resource-new',
    component: () => import('../views/ResourceEditView.vue'),
    meta: { title: '发布资料', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/resources/edit/:id',
    name: 'resource-edit',
    component: () => import('../views/ResourceEditView.vue'),
    meta: { title: '编辑资料', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/resources/:id',
    name: 'resource-detail',
    component: () => import('../views/ResourceDetailView.vue'),
    meta: { title: '资料详情', requiresAuth: true, hideTabbar: true },
  },

  // 社区
  {
    path: '/posts',
    name: 'posts',
    component: () => import('../views/PostsView.vue'),
    meta: { title: '动态', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/posts/:id',
    name: 'post-detail',
    component: () => import('../views/PostDetailView.vue'),
    meta: { title: '动态详情', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/inspirations',
    name: 'inspirations',
    component: () => import('../views/InspirationView.vue'),
    meta: { title: '励志区', requiresAuth: true, hideTabbar: true },
  },
  {
    path: '/dream-wall',
    name: 'dream-wall',
    component: () => import('../views/DreamWallView.vue'),
    meta: { title: '梦校墙', requiresAuth: true, hideTabbar: true },
  },

  // 登录 / 注册 / 找回（无底部导航）
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/auth/AuthView.vue'),
    meta: { title: '登录', hideTabbar: true },
  },
  // 后台管理（仅管理员，页面内二次校验）
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminView.vue'),
    meta: { title: '后台管理', requiresAuth: true, requiresAdmin: true, hideTabbar: true },
  },
  {
    path: '/admin/email-jobs',
    name: 'email-jobs',
    component: () => import('../views/EmailJobsView.vue'),
    meta: { title: '通知邮件任务', requiresAuth: true, requiresAdmin: true, hideTabbar: true },
  },

  // 二级页（隐藏底部导航）
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('../views/TasksView.vue'),
    meta: { title: '任务计划', hideTabbar: true },
  },
  {
    path: '/mistakes',
    name: 'mistakes',
    component: () => import('../views/MistakesView.vue'),
    meta: { title: '错题本', hideTabbar: true },
  },
  {
    path: '/mistake/edit',
    name: 'mistake-edit',
    component: () => import('../views/MistakeEditView.vue'),
    meta: { title: '记一道错题', hideTabbar: true },
  },
  {
    path: '/subjects',
    name: 'subjects',
    component: () => import('../views/SubjectManageView.vue'),
    meta: { title: '科目管理', hideTabbar: true },
  },
  {
    path: '/settings/learning',
    name: 'learning-settings',
    component: () => import('../views/LearningSettingsView.vue'),
    meta: { title: '专注与休息设置', hideTabbar: true },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

// 默认所有业务页均需登录。已经登录的账号仍可使用自己的离线学习数据。
router.beforeEach((to) => authorizeRoute(to, useAuthStore()));

export default router;
