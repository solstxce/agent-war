import { existsSync, readFileSync, writeFileSync, appendFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dir, '..')
for (const [example, local] of [
  ['frontend/.env.example', 'frontend/.env.local'],
  ['backend/.env.example', 'backend/.env'],
]) {
  const source = readFileSync(resolve(root, example), 'utf8')
  const destination = resolve(root, local)
  if (!existsSync(destination)) {
    writeFileSync(destination, source)
    console.log(`Created ${local}`)
    continue
  }
  const existing = readFileSync(destination, 'utf8')
  const keys = new Set([...existing.matchAll(/^([A-Z][A-Z0-9_]*)=/gm)].map(match => match[1]))
  const missing = source.split(/\r?\n/).filter(line => {
    const match = /^([A-Z][A-Z0-9_]*)=/.exec(line)
    return match && !keys.has(match[1])
  })
  if (missing.length) appendFileSync(destination, `\n# Additional integration settings\n${missing.join('\n')}\n`)
  console.log(`${local}: ${missing.length} settings added; existing values preserved`)
}
