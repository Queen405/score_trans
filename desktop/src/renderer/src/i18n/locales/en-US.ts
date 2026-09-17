import type zhMessages from './zh-CN'
import app from './en-US/app'
import common from './en-US/common'
import components from './en-US/components'
import convert from './en-US/convert'
import recognize from './en-US/recognize'
import runtime from './en-US/runtime'
import settings from './en-US/settings'
import syntax from './en-US/syntax'

const messages: typeof zhMessages = {
  app,
  common,
  components,
  convert,
  recognize,
  runtime,
  settings,
  syntax,
}

export default messages
