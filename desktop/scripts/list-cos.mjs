#!/usr/bin/env node
import COS from 'cos-nodejs-sdk-v5'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = resolve(__dirname, '..', '..')

function loadEnv() {
  const envPath = join(PROJECT_ROOT, '.env')
  if (!existsSync(envPath)) process.exit(1)
  const parsed = {}
  for (const line of readFileSync(envPath, 'utf8').split(/\r?\n/)) {
    const l = line.trim()
    if (!l || l.startsWith('#')) continue
    const eq = l.indexOf('=')
    if (eq <= 0) continue
    const k = l.slice(0, eq).trim()
    let v = l.slice(eq + 1).trim()
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'")))
      v = v.slice(1, -1)
    parsed[k] = v
  }
  return parsed
}

const env = loadEnv()
const cos = new COS({ SecretId: env.TENCENTCLOUD_SECRET_ID, SecretKey: env.TENCENTCLOUD_SECRET_KEY })
const BUCKET = env.COS_BUCKET || 'score-trans-1320022301'
const REGION = env.COS_REGION || 'ap-beijing'

cos.getBucket(
  { Bucket: BUCKET, Region: REGION, Prefix: 'download/', MaxKeys: 100 },
  (err, data) => {
    if (err) {
      console.error('失败:', err.message)
      process.exit(1)
    }
    console.log(`download/ 前缀下共 ${data.Contents?.length || 0} 个对象:`)
    for (const item of data.Contents || []) {
      const sizeMB = (Number(item.Size) / 1048576).toFixed(1)
      console.log(`  ${item.Key}  (${sizeMB} MB)  [${item.LastModified}]`)
    }
  },
)
