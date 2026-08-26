import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { NModal, NButton } from 'naive-ui'

const app = createSSRApp({
  render() {
    return h(NModal, {
      preset: 'card',
      title: '有更改尚未保存',
      bordered: false,
      show: true,
    }, {
      default: () => h('p', '当前有更改未保存，重置将丢弃这些修改，是否继续？'),
      footer: () => h('div', { class: 'discard-confirm-actions' }, [
        h(NButton, null, { default: () => '取消' }),
        h(NButton, { type: 'warning' }, { default: () => '继续' }),
      ])
    })
  }
})

renderToString(app).then(html => {
  console.log(html)
}).catch(e => console.error('ERR', e.message))
