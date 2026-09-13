#!/usr/bin/env node
/**
 * 验证 cos-nodejs-sdk-v5 是否可用（只读操作，不上传/不删除）。
 */
import COS from 'cos-nodejs-sdk-v5'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const DESKTOP_DIR = resolve(__dirname, '..')
const PROJECT_ROOT = resolve(DESKTOP_DIR, '..')

function resolve(...args) {
  return args.reduce((a, b) => join(a, b))
}

// 从项目根 .env 读取密钥
function loadEnv() {
  const envPath = join(PROJECT_ROOT, '.env')
  if (!existsSync(envPath)) {
    console.error('找不到 .env 文件')
    process.exit(1)
  }
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
const SECRET_ID = env.TENCENTCLOUD_SECRET_ID
const SECRET_KEY = env.TENCENTCLOUD_SECRET_KEY
const BUCKET = env.COS_BUCKET || 'score-trans-1320022301'
const REGION = env.COS_REGION || 'ap-beijing'

if (!SECRET_ID || !SECRET_KEY) {
  console.error('缺少 TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY')
  process.exit(1)
}

const cos = new COS({
  SecretId: SECRET_ID,
  SecretKey: SECRET_KEY,
})

console.log('--- cos-nodejs-sdk-v5 可用性测试 ---\n')
console.log(`Bucket : ${BUCKET}`)
console.log(`Region : ${REGION}\n`)

// 1. headBucket —— 检查 Bucket 是否可访问
console.log('[1/2] headBucket ...')
cos.headBucket(
  { Bucket: BUCKET, Region: REGION },
  (err, data) => {
    if (err) {
      console.error('  失败:', err.statusCode, err.message?.slice(0, 200))
      console.error('\n  SDK 不可用或密钥/配置有误。')
      process.exit(1)
    }
    console.log('  成功 ✓  Bucket 可访问 (statusCode', data.statusCode + ')')

    // 2. getBucket —— 列出前 5 个对象（只读）
    console.log('\n[2/2] getBucket (列前 5 个对象) ...')
    cos.getBucket(
      {
        Bucket: BUCKET,
        Region: REGION,
        Prefix: '',
        MaxKeys: 5,
      },
      (err2, data2) => {
        if (err2) {
          console.error('  失败:', err2.statusCode, err2.message?.slice(0, 200))
          process.exit(1)
        }
        console.log('  成功 ✓  共 ' + (data2.Contents?.length || 0) + ' 个对象:')
        for (const item of data2.Contents || []) {
          const sizeKB = (Number(item.Size) / 1024).toFixed(1)
          console.log(`    ${item.Key}  (${sizeKB} KB)`)
        }
        console.log('\n--- SDK 可用，测试通过 ---')
      },
    )
  },
)
