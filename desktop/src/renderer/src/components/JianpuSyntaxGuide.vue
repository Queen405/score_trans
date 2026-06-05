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
        <p>使用纯文本描述简谱，渲染为 SVG 谱面。设计理念：<strong>看到什么符号，就输入什么符号</strong>。</p>
      </div>

      <div class="guide-section">
        <h3>快速开始</h3>
        <pre><code>title=小星星
1=C
4/4
tempo=100

1 1 5 5 | 6 6 h5 | 4 4 3 3 | 2 2 h1 |
L: 一 闪 一 闪 亮 晶 晶</code></pre>
      </div>

      <div class="guide-grid">
        <section>
          <h3>谱面信息</h3>
          <table>
            <tbody>
              <tr><td><code>1=C</code></td><td>调号（大调主音）</td></tr>
              <tr><td><code>4/4</code></td><td>拍号</td></tr>
              <tr><td><code>title=名称</code></td><td>谱名，可选</td></tr>
              <tr><td><code>tempo=120</code></td><td>速度（BPM），可选</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3>音符与八度</h3>
          <table>
            <tbody>
              <tr><td><code>1</code>–<code>7</code></td><td>do–si 七个音级</td></tr>
              <tr><td><code>0</code></td><td>休止符</td></tr>
              <tr><td><code>1'</code> <code>2'</code></td><td>高八度（上加点）</td></tr>
              <tr><td><code>1,</code> <code>2,</code></td><td>低八度（下加点）</td></tr>
              <tr><td><code>#1</code> <code>b7</code></td><td>升、降半音</td></tr>
              <tr><td><code>x4</code> <code>bb7</code></td><td>重升、重降</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3>时值控制</h3>
          <table>
            <tbody>
              <tr><td><code>w1</code></td><td>全音符（4 拍）</td></tr>
              <tr><td><code>h1</code></td><td>二分音符（2 拍）</td></tr>
              <tr><td><code>1</code></td><td>四分音符（1 拍，默认）</td></tr>
              <tr><td><code>q1</code></td><td>八分音符（½ 拍）</td></tr>
              <tr><td><code>s1</code></td><td>十六分音符（¼ 拍）</td></tr>
              <tr><td><code>d1</code></td><td>三十二分音符（⅛ 拍）</td></tr>
              <tr><td><code>5.</code></td><td>附点（延长自身一半）</td></tr>
              <tr><td><code>5~</code> / <code>~5</code></td><td>延音线起 / 止</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3>和弦与小节</h3>
          <table>
            <tbody>
              <tr><td><code>[1+3+5]</code></td><td>和弦（音纵向排列）</td></tr>
              <tr><td><code>q[1+3+5]</code></td><td>带时值的和弦</td></tr>
              <tr><td><code>|</code></td><td>小节线</td></tr>
              <tr><td><code>||</code></td><td>终止线</td></tr>
              <tr><td><code>|: :|</code></td><td>反复起止</td></tr>
            </tbody>
          </table>
        </section>
      </div>

      <div class="guide-grid lower">
        <section>
          <h3>装饰标记</h3>
          <table>
            <tbody>
              <tr><td><code>(1 2 3)</code></td><td>连音线（圆滑奏）</td></tr>
              <tr><td><code>\p</code> <code>\f</code></td><td>弱 / 强</td></tr>
              <tr><td><code>\mp</code> <code>\mf</code></td><td>中弱 / 中强</td></tr>
              <tr><td><code>\ff</code> <code>\sfz</code></td><td>很强 / 突强</td></tr>
              <tr><td><code>^.</code></td><td>断奏（staccato）</td></tr>
              <tr><td><code>^></code></td><td>重音（accent）</td></tr>
              <tr><td><code>^-</code></td><td>保持（tenuto）</td></tr>
              <tr><td><code>^tr</code></td><td>颤音（trill）</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3>歌词与注释</h3>
          <table>
            <tbody>
              <tr><td><code>L: 春 风 又 绿</code></td><td>歌词行，按音符顺序匹配</td></tr>
              <tr><td><code># 注释内容</code></td><td>注释行，解析时忽略</td></tr>
            </tbody>
          </table>
          <p class="section-note">歌词与音符按顺序一一对应；休止符不分配歌词。</p>
        </section>
      </div>

      <div class="guide-section">
        <h3>完整示例</h3>
        <pre><code>title=练习曲
1=G
4/4

\mf 1 2 3 4 | q5 q5 q3 q1 q5 q5 q3 q1 | h2. q3 q4 | w1 |
L: 春 眠 不 觉 晓 处 处 闻 啼 鸟 飞 飞 飞 去 去 去

\p (5 6 5 4) | 3 2 1 ~1 | 2 3 4 3 | h2 h0 |
L: 夜 来 风 雨 声 花 落 知 多 少 安 睡 吧</code></pre>
      </div>

      <div class="guide-section quick-ref">
        <h3>速查表</h3>
        <div class="ref-grid">
          <div><code>1</code>–<code>7</code> 音级　<code>0</code> 休止</div>
          <div><code>'</code> <code>,</code> 八度　<code>#</code> <code>b</code> <code>x</code> <code>bb</code> 升降</div>
          <div><code>q</code> <code>s</code> <code>d</code> <code>h</code> <code>w</code> 时值前缀</div>
          <div><code>.</code> 附点　<code>~</code> 延音线　<code>( )</code> 连音线</div>
          <div><code>[a+b]</code> 和弦　<code>| || |: :|</code> 小节线</div>
          <div><code>\p \f</code> 力度　<code>^. ^> ^- ^tr</code> 演奏法</div>
          <div><code>L:</code> 歌词　<code>#</code> 注释</div>
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

.guide-intro p {
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
  grid-template-columns: repeat(2, minmax(360px, 1fr));
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
  padding: 5px 0;
  border-top: 1px solid var(--border-soft);
  color: var(--text-secondary);
  line-height: 1.5;
  vertical-align: top;
}

tr:first-child td {
  border-top: 0;
}

td:first-child {
  width: 42%;
  color: var(--text-primary);
  padding-right: 8px;
  white-space: nowrap;
}

.section-note {
  margin: 8px 0 0;
  font-size: 11.5px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

ul {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.guide-section.warn {
  background: color-mix(in srgb, var(--warn-bg, #fff8e1) 60%, transparent);
  border-color: color-mix(in srgb, var(--warn-border, #ffe082) 60%, transparent);
}

.guide-section.warn h3 {
  color: var(--warn-text, #e65100);
}

.quick-ref .ref-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 16px;
}

.quick-ref .ref-grid div {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 760px) {
  .guide-grid,
  .guide-grid.lower {
    grid-template-columns: 1fr;
  }

  td:first-child {
    width: 46%;
  }

  .quick-ref .ref-grid {
    grid-template-columns: 1fr;
  }
}
</style>
