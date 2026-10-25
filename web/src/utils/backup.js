import { blobToDataUrl } from './image'

// 所有本地题图和解析图都可序列化后才生成备份；读取失败时不产出残缺文件。
export async function buildBackup(database, settings) {
  const [subjects, sessions, tasks, rows] = await Promise.all([
    database.subjects.toArray(), database.sessions.toArray(),
    database.tasks.toArray(), database.mistakes.toArray(),
  ])
  const mistakes = []
  for (const row of rows) {
    const item = { ...row }
    for (const field of ['images', 'answerImages']) {
      item[field] = await Promise.all((row[field] || []).map((image) =>
        typeof image === 'string' ? image : blobToDataUrl(image)))
    }
    mistakes.push(item)
  }
  return {
    app: 'yanshi', version: 3, exportedAt: new Date().toISOString(), settings,
    subjects, sessions, tasks, mistakes,
  }
}
