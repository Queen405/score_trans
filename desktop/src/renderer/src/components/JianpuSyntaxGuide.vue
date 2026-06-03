<template>
  <n-modal
    :show="show"
    preset="dialog"
    class="syntax-guide-modal"
    title="简谱编辑语法说明"
    :show-icon="false"
    positive-text="知道了"
    @positive-click="$emit('update:show', false)"
    @update:show="$emit('update:show', $event)"
  >
    <div class="guide-shell">
      <div class="guide-intro">
        <p>编辑器使用项目自研简谱语法，借鉴文本谱编辑工具的写法：先写调号和拍号，再按小节输入音符。OCR 文字不写在这里，仍在渲染画面中单独拖动、缩放和保存。</p>
      </div>

      <div class="guide-section">
        <h3>快速开始</h3>
        <pre><code>title=瑞雪迎春
1=C
4/4
1 2 q3 q4 | h[1+3+5] \p |
L: 春 风 又 绿</code></pre>
      </div>

      <div class="guide-grid">
        <section>
          <h3>头部</h3>
          <table>
            <tbody>
              <tr><td><code>title=瑞雪迎春</code></td><td>谱名，可选</td></tr>
              <tr><td><code>1=C</code></td><td>调号，必写或默认 C</td></tr>
              <tr><td><code>4/4</code></td><td>拍号，必写或默认 4/4</td></tr>
              <tr><td><code>tempo=85</code></td><td>速度，可选</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3>音符</h3>
          <table>
            <tbody>
              <tr><td><code>1 2 3</code></td><td>基础音级</td></tr>
              <tr><td><code>0</code></td><td>休止符</td></tr>
              <tr><td><code>#1 b2 n7</code></td><td>升、降、还原</td></tr>
              <tr><td><code>1' 1,</code></td><td>高八度、低八度</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3>时值</h3>
          <table>
            <tbody>
              <tr><td><code>w1</code></td><td>全音符</td></tr>
              <tr><td><code>h1</code></td><td>二分音符</td></tr>
              <tr><td><code>1</code></td><td>四分音符</td></tr>
              <tr><td><code>q1 s1 d1</code></td><td>八分、十六分、三十二分</td></tr>
              <tr><td><code>1. q2.</code></td><td>附点</td></tr>
              <tr><td><code>1- 1---</code></td><td>延长</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3>和弦与小节</h3>
          <table>
            <tbody>
              <tr><td><code>[1+3+5]</code></td><td>和弦</td></tr>
              <tr><td><code>q[#2+4'+6]</code></td><td>带时值、升降、八度的和弦</td></tr>
              <tr><td><code>| || |: :|</code></td><td>普通、终止、反复小节线</td></tr>
            </tbody>
          </table>
        </section>
      </div>

      <div class="guide-grid lower">
        <section>
          <h3>连线、歌词、力度</h3>
          <table>
            <tbody>
              <tr><td><code>1~ 1</code></td><td>延音线</td></tr>
              <tr><td><code>(1 2 3)</code></td><td>圆滑线</td></tr>
              <tr><td><code>L: 春 风 又 绿</code></td><td>歌词行，按音符顺序匹配</td></tr>
              <tr><td><code>\p \mp \f \ff</code></td><td>力度标记</td></tr>
              <tr><td><code>^tr ^&gt; ^-</code></td><td>颤音、重音、保持音</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3>常见错误</h3>
          <ul>
            <li><code>key=C</code>、<code>time=4/4</code> 是旧写法，保存或打开历史时会自动迁移。</li>
            <li><code>1/</code>、<code>1//</code> 是旧时值，推荐写成 <code>q1</code>、<code>s1</code>。</li>
            <li>和弦时值写在和弦前，例如 <code>q[1+3+5]</code>，不要写成 <code>[1/+3/]</code>。</li>
            <li>OCR 文字不要写入简谱编辑器，在渲染界面中直接编辑和拖动。</li>
          </ul>
        </section>
      </div>

      <div class="guide-section refs">
        <h3>参考资料</h3>
        <p>说明结构参考了 LilyPond 的“文本输入、学习手册、语法参考”分层，abcjs 对 ABC 标准兼容性/例外的说明方式，以及 VexTab 教程的逐步示例和可写性导向。</p>
        <div class="ref-links">
          <a href="https://lilypond.org/manuals" target="_blank">LilyPond Manuals</a>
          <a href="https://docs.abcjs.net/overview/abc-notation" target="_blank">abcjs ABC Notation</a>
          <a href="https://www.vexflow.com/vextab/tutorial.html" target="_blank">VexTab Tutorial</a>
          <a href="https://github.com/ssb22/jianpu-ly" target="_blank">jianpu-ly</a>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { NModal } from 'naive-ui'

defineProps<{ show: boolean }>()
defineEmits<{ 'update:show': [value: boolean] }>()
</script>

<style scoped>
:global(.syntax-guide-modal.n-dialog) {
  width: min(1080px, calc(100vw - 96px));
  max-width: min(1080px, calc(100vw - 96px));
}

.guide-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: min(72vh, 760px);
  overflow: auto;
  padding-right: 4px;
}

.guide-intro p,
.refs p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.guide-section,
.guide-grid section {
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 12px;
  background: color-mix(in srgb, var(--bg-panel) 86%, transparent);
}

.guide-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(360px, 1fr));
  gap: 12px;
}

.guide-grid.lower {
  grid-template-columns: minmax(420px, 1.1fr) minmax(360px, 0.9fr);
}

h3 {
  margin: 0 0 9px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

pre {
  margin: 0;
  padding: 12px;
  overflow: auto;
  border-radius: var(--radius-sm);
  background: var(--bg-base);
  border: 1px solid var(--border-soft);
  line-height: 1.7;
}

code {
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

td {
  padding: 6px 0;
  border-top: 1px solid var(--border-soft);
  color: var(--text-secondary);
  line-height: 1.5;
  vertical-align: top;
}

tr:first-child td {
  border-top: 0;
}

td:first-child {
  width: 38%;
  color: var(--text-primary);
  padding-right: 10px;
  white-space: nowrap;
}

ul {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.ref-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.ref-links a {
  color: var(--accent);
  text-decoration: none;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 5px 8px;
  background: var(--bg-base);
}

@media (max-width: 760px) {
  .guide-grid,
  .guide-grid.lower {
    grid-template-columns: 1fr;
  }

  td:first-child {
    width: 42%;
  }
}
</style>
