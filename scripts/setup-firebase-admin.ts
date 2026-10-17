import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { isAbsolute, relative, resolve } from 'node:path'

const root = resolve(import.meta.dir, '..')
const input = process.argv[2]
if (!input || !isAbsolute(input)) {
  console.error('Usage: bun run setup:firebase-admin "C:/absolute/path/to/service-account.json"')
  process.exit(1)
}
try {
  const filename = resolve(input)
  const relativeFilename = relative(root, filename)
  if (!relativeFilename.startsWith('..') && !isAbsolute(relativeFilename)) throw new Error('Keep the private credential file outside this repository.')
  const credential = JSON.parse(readFileSync(filename, 'utf8').replace(/^\uFEFF/, ''))
  if (credential.type !== 'service_account' || !credential.private_key || !credential.client_email || !credential.project_id) {
    throw new Error('This is not a Firebase service-account key. Download it from Project settings > Service accounts > Generate new private key. Android google-services.json is not the backend credential.')
  }
  const frontendEnv = resolve(root, 'frontend/.env.local')
  const frontendProject = existsSync(frontendEnv)
    ? /^VITE_FIREBASE_PROJECT_ID=(.*)$/m.exec(readFileSync(frontendEnv, 'utf8'))?.[1]?.trim().replace(/^['"]|['"]$/g, '')
    : undefined
  if (frontendProject && frontendProject !== credential.project_id) throw new Error('The credential project does not match frontend/.env.local. Select the matching Firebase project.')
  const destination = resolve(root, 'backend/.env')
  const values: Record<string, string> = {
    GOOGLE_APPLICATION_CREDENTIALS: JSON.stringify(filename.replaceAll('\\', '/')),
    FIREBASE_PROJECT_ID: credential.project_id,
    FIREBASE_AUTH_EMULATOR_HOST: '',
    FIRESTORE_EMULATOR_HOST: '',
  }
  const found = new Set<string>()
  const lines = (existsSync(destination) ? readFileSync(destination, 'utf8') : '').split(/\r?\n/).map(line => {
    const key = line.split('=', 1)[0]
    if (!(key in values)) return line
    found.add(key)
    return `${key}=${values[key]}`
  })
  for (const [key, value] of Object.entries(values)) if (!found.has(key)) lines.push(`${key}=${value}`)
  writeFileSync(destination, `${lines.join('\n').trimEnd()}\n`)
  console.log('Backend credential path configured for the matching Firebase project. Restart the backend. No private-key contents were copied.')
} catch (error) {
  console.error(error instanceof Error ? error.message : 'Could not configure the credential file.')
  process.exit(1)
}
