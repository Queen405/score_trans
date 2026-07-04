import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { migrateLegacyDataDirectory } from '../src/main/storageMigration.mts'

test('legacy user data migration is idempotent and preserves conflicts', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'score-trans-storage-'))
  const legacy = path.join(root, '.sorce_trans')
  const target = path.join(root, '.score_trans')
  fs.mkdirSync(path.join(legacy, 'work'), { recursive: true })
  fs.mkdirSync(path.join(target, 'work'), { recursive: true })
  fs.writeFileSync(path.join(legacy, 'work', 'history.db'), 'legacy-history')
  fs.writeFileSync(path.join(legacy, 'work', 'settings.db'), 'legacy-settings')
  fs.writeFileSync(path.join(target, 'work', 'settings.db'), 'new-settings')

  try {
    assert.equal(migrateLegacyDataDirectory(legacy, target), true)
    assert.equal(migrateLegacyDataDirectory(legacy, target), true)
    assert.equal(
      fs.readFileSync(path.join(target, 'work', 'history.db'), 'utf-8'),
      'legacy-history',
    )
    assert.equal(
      fs.readFileSync(path.join(target, 'work', 'settings.db'), 'utf-8'),
      'new-settings',
    )
    assert.equal(
      fs.readFileSync(path.join(legacy, 'work', 'settings.db'), 'utf-8'),
      'legacy-settings',
    )
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('legacy user data migration refuses symbolic links', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'score-trans-storage-'))
  const legacy = path.join(root, '.sorce_trans')
  const target = path.join(root, '.score_trans')
  const external = path.join(root, 'external.txt')
  fs.mkdirSync(legacy, { recursive: true })
  fs.writeFileSync(external, 'outside')

  try {
    try {
      fs.symlinkSync(external, path.join(legacy, 'linked.txt'))
    } catch (error) {
      if (error?.code === 'EPERM') {
        t.skip('Windows symbolic-link permission is unavailable')
        return
      }
      throw error
    }
    assert.equal(migrateLegacyDataDirectory(legacy, target), false)
    assert.equal(fs.existsSync(path.join(target, 'linked.txt')), false)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})
