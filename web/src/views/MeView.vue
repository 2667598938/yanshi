<script setup>
import { useAuthStore } from '../stores/auth'
import {useRouter} from 'vue-router'
import ProfileCard from '../components/ProfileCard.vue'
import { ChevronRight, SlidersHorizontal, BookOpen, UserRound, Users, Database } from 'lucide-vue-next'
const auth=useAuthStore()
const router=useRouter()
const categories=[
 {id:'learning',name:'学习设置',description:'专注休息 · 通知 · 科目',icon:SlidersHorizontal},
 {id:'content',name:'学习内容',description:'梦校 · 收藏 · 学习记录',icon:BookOpen},
 {id:'account',name:'账号与会员',description:'个人资料 · VIP · AI 设置',icon:UserRound},
 {id:'group',name:'小组与自习室',description:'小组准入 · 共享与隐私',icon:Users},
 {id:'data',name:'数据与关于',description:'同步 · 备份恢复 · 协议 · 退出',icon:Database},
]
</script>
<template><div class="page me-overview"><header><h1>我的</h1></header><ProfileCard @edit="router.push({path:'/me/account',query:{edit:'profile'}})"/>
<nav aria-label="我的设置分类"><router-link v-for="item in categories" :key="item.id" :to="'/me/'+item.id" class="card category-link"><component :is="item.icon" :size="24"/><span><strong>{{item.name}}</strong><small>{{item.description}}</small></span><ChevronRight :size="20"/></router-link></nav></div></template>
<style scoped>
.me-overview{max-width:800px;margin:auto}h1{font-size: 24px;line-height:32px;margin:0 0 8px}header{margin-bottom:16px}header a{display:flex;align-items:center;color:var(--sub);font-size: 14px;text-decoration:none}
nav{display:grid;gap:0;margin-top:20px;border:1px solid rgba(255,255,255,.85);border-radius:24px;overflow:hidden;background:var(--glass);backdrop-filter:blur(20px);box-shadow:var(--shadow-soft)}.category-link{display:flex;align-items:center;gap:16px;text-decoration:none;color:var(--ink);padding:16px;min-height:76px;border:0;border-radius:0;background:transparent;box-shadow:none;margin:0!important}.category-link+.category-link{border-top:1px solid var(--line)}.category-link>svg:first-child{color:var(--primary)}.category-link span{flex:1}.category-link strong{display:block;font-size:16px}.category-link small{display:block;font-size:12px;color:var(--sub);margin-top:4px}
</style>
