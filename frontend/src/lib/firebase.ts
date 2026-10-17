import { getApps, initializeApp } from 'firebase/app'
import { connectAuthEmulator, getAuth } from 'firebase/auth'
import { connectFirestoreEmulator, getFirestore } from 'firebase/firestore'

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}
export const firebaseConfigured = Object.values(config).every(Boolean)
export const firebaseApp = firebaseConfigured ? (getApps()[0] ?? initializeApp({ ...config, messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID, storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET })) : null
export const auth = firebaseApp ? getAuth(firebaseApp) : null
export const db = firebaseApp ? getFirestore(firebaseApp) : null
const emulatorState = globalThis as typeof globalThis & { __relayEmulatorsConnected?: boolean }
if (import.meta.env.DEV && import.meta.env.VITE_USE_FIREBASE_EMULATORS === 'true' && auth && db && !emulatorState.__relayEmulatorsConnected) {
  connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true })
  connectFirestoreEmulator(db, '127.0.0.1', 8080)
  emulatorState.__relayEmulatorsConnected = true
}
