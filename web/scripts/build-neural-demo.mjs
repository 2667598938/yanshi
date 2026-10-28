// 生成完全离线、单文件的视觉演示，复用真实AI页样式；不调用接口或加载用户数据。
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
const root = new URL('../', import.meta.url)
const css = readFileSync(new URL('src/assets/styles/ai-neural.css', root), 'utf8')
const template = readFileSync(new URL('scripts/neural-demo.template.html', root), 'utf8')
mkdirSync(new URL('public/previews/', root), { recursive: true })
writeFileSync(new URL('public/previews/ai-neural.html', root), template.replace('/* NEURAL_CSS */', css))
