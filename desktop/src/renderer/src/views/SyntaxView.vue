<template>
  <div class="settings-view">
    <aside
      class="sv-sidebar"
      aria-label="语法章节"
    >
      <div class="sv-sidebar-header">
        <span class="sv-sidebar-eyebrow">语法参考</span>
        <h2>语法说明</h2>
      </div>

      <nav class="sv-category-list">
        <button
          v-for="section in docSections"
          :key="section.id"
          type="button"
          :class="['sv-category-button', { active: activeSection === section.id }]"
          :aria-current="activeSection === section.id ? 'page' : undefined"
          @click="activeSection = section.id"
        >
          <n-icon size="18">
            <component :is="section.icon" />
          </n-icon>
          <span>{{ section.label }}</span>
        </button>
      </nav>
    </aside>

    <section class="sv-main syntax-main">
      <header class="sv-page-header syntax-page-header">
        <div>
          <h1>{{ activeMeta.label }}</h1>
        </div>
        <n-input
          v-model:value="searchQuery"
          class="syntax-search"
          clearable
          placeholder="搜索语法、名称或说明"
          aria-label="搜索简谱语法"
        >
          <template #prefix>
            <n-icon :component="SearchOutline" />
          </template>
        </n-input>
      </header>

      <div class="sv-page-body">
        <div class="sv-panel-container">
          <div
            v-if="normalizedQuery"
            class="syntax-search-results"
            aria-live="polite"
          >
            <div class="syntax-search-header">
              <div>
                <p class="syntax-search-kicker">
                  搜索结果
                </p>
                <h3>找到 {{ searchResultCount }} 条相关语法</h3>
              </div>
              <n-button
                size="small"
                quaternary
                @click="searchQuery = ''"
              >
                清除搜索
              </n-button>
            </div>

            <template v-if="searchResultCount">
              <section
                v-for="group in searchGroups"
                :key="group.key"
                class="result-group"
              >
                <h4>{{ group.title }}</h4>
                <div class="result-list">
                  <button
                    v-for="item in group.items"
                    :key="item.key"
                    type="button"
                    class="result-row"
                    @click="openSearchResult(item)"
                  >
                    <code>{{ item.syntax }}</code>
                    <span class="result-copy">
                      <strong>{{ item.name }}</strong>
                      <span>{{ item.description }}</span>
                    </span>
                    <span class="result-section">{{ item.sectionTitle }}</span>
                  </button>
                </div>
              </section>
            </template>

            <n-empty
              v-else
              description="没有找到匹配的语法"
            >
              <template #extra>
                <n-button
                  size="small"
                  @click="searchQuery = ''"
                >
                  返回完整说明
                </n-button>
              </template>
            </n-empty>
          </div>

          <div
            v-else
            class="sv-panel"
          >
            <section
              v-if="activeSection === 'quick-start'"
              class="syntax-section"
            >
              <div class="code-block">
                <div class="code-toolbar">
                  <span>简谱文本</span>
                  <n-tooltip>
                    <template #trigger>
                      <button
                        type="button"
                        class="copy-button"
                        :aria-label="copiedBlock === 'quick' ? '已复制' : '复制示例'"
                        @click="copyExample('quick', quickStartExample)"
                      >
                        <n-icon :component="copiedBlock === 'quick' ? CheckmarkOutline : CopyOutline" />
                      </button>
                    </template>
                    {{ copiedBlock === 'quick' ? '已复制' : '复制示例' }}
                  </n-tooltip>
                </div>
                <pre><code>{{ quickStartExample }}</code></pre>
              </div>
            </section>

            <section
              v-else-if="activeTableSection"
              class="syntax-section"
            >
              <div class="table-wrap">
                <table class="syntax-table">
                  <thead>
                    <tr>
                      <th>语法</th>
                      <th>含义</th>
                      <th>说明或示例</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="entry in activeTableSection.entries"
                      :key="`${activeTableSection.id}-${entry.syntax}`"
                    >
                      <td><code>{{ entry.syntax }}</code></td>
                      <td>{{ entry.name }}</td>
                      <td>{{ entry.description }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section
              v-else-if="activeSection === 'performance-marks'"
              class="syntax-section"
            >
              <div
                v-if="loadingProfiles"
                class="profile-loading"
                aria-label="正在加载演奏技巧"
              >
                <n-skeleton
                  v-for="index in 5"
                  :key="index"
                  text
                  :repeat="1"
                />
              </div>

              <div
                v-else-if="profileError"
                class="inline-state"
                role="alert"
              >
                <div>
                  <strong>演奏技巧暂时无法加载</strong>
                  <p>{{ profileError }}</p>
                </div>
                <n-button
                  size="small"
                  secondary
                  :loading="loadingProfiles"
                  @click="loadProfiles"
                >
                  重新加载
                </n-button>
              </div>

              <n-empty
                v-else-if="!orderedProfiles.length"
                description="当前没有可用的乐器语法"
              />

              <n-tabs
                v-else
                v-model:value="activeProfile"
                type="line"
                animated
              >
                <n-tab-pane
                  v-for="profile in orderedProfiles"
                  :key="profile.id"
                  :name="profile.id"
                  :tab="profile.name"
                >
                  <div class="profile-meta">
                    <span>谱面元数据</span>
                    <code>instrument={{ profileIdForText(profile.id) }}</code>
                  </div>

                  <div
                    v-if="profile.marks?.length"
                    class="table-wrap"
                  >
                    <table class="syntax-table profile-table">
                      <thead>
                        <tr>
                          <th>语法</th>
                          <th>技巧</th>
                          <th>记谱说明</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="mark in profile.marks"
                          :key="mark.id"
                        >
                          <td><code>{{ mark.syntax }}</code></td>
                          <td>{{ mark.name }}</td>
                          <td>{{ mark.description }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <n-empty
                    v-else
                    description="该模式没有专属演奏技巧"
                  />

                  <div
                    v-if="profile.range_examples?.length || profile.combination_examples?.length"
                    class="profile-examples"
                  >
                    <div
                      v-if="profile.range_examples?.length"
                      class="example-list"
                    >
                      <h3>范围写法</h3>
                      <div
                        v-for="example in profile.range_examples"
                        :key="`range-${example.syntax}`"
                        class="example-row"
                      >
                        <code>{{ example.syntax }}</code>
                        <span>{{ example.description }}</span>
                      </div>
                    </div>
                    <div
                      v-if="profile.combination_examples?.length"
                      class="example-list"
                    >
                      <h3>组合示例</h3>
                      <div
                        v-for="example in profile.combination_examples"
                        :key="`combination-${example.syntax}`"
                        class="example-row"
                      >
                        <code>{{ example.syntax }}</code>
                        <span>{{ example.description }}</span>
                      </div>
                    </div>
                  </div>
                </n-tab-pane>
              </n-tabs>
            </section>

            <section
              v-else-if="activeSection === 'quick-reference'"
              class="syntax-section"
            >
              <div class="table-wrap">
                <table class="syntax-table">
                  <thead>
                    <tr>
                      <th>语法</th>
                      <th>含义</th>
                      <th>备注</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="entry in quickReferenceEntries"
                      :key="`quick-${entry.syntax}`"
                    >
                      <td><code>{{ entry.syntax }}</code></td>
                      <td>{{ entry.name }}</td>
                      <td>{{ entry.description }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import {
  AppsOutline,
  CheckmarkOutline,
  ColorWandOutline,
  CopyOutline,
  CreateOutline,
  FlashOutline,
  InformationCircleOutline,
  ListOutline,
  MusicalNotesOutline,
  SearchOutline,
  TimerOutline,
} from '@vicons/ionicons5'
import {
  NButton,
  NEmpty,
  NIcon,
  NInput,
  NSkeleton,
  NTabPane,
  NTabs,
  NTooltip,
  useMessage,
} from 'naive-ui'
import { requireData } from '../api/client'
import { notationApi } from '../api/notation'
import type { InstrumentProfileCatalog } from '../models/types'

type SectionId =
  | 'quick-start'
  | 'metadata'
  | 'notes'
  | 'duration'
  | 'measures'
  | 'expression'
  | 'performance-marks'
  | 'quick-reference'

interface DocSection {
  id: SectionId
  label: string
  icon: Component
}

interface SyntaxEntry {
  syntax: string
  name: string
  description: string
  keywords?: string[]
}

interface SyntaxSection {
  id: SectionId
  title: string
  kicker: string
  entries: SyntaxEntry[]
}

interface SearchItem {
  key: string
  groupKey: string
  groupTitle: string
  sectionId: SectionId
  sectionTitle: string
  syntax: string
  name: string
  description: string
  keywords: string[]
  profileId?: string
}

interface SearchGroup {
  key: string
  title: string
  items: SearchItem[]
}

const message = useMessage()
const searchQuery = ref('')
const activeSection = ref<SectionId>('quick-start')
const profiles = ref<InstrumentProfileCatalog[]>([])
const activeProfile = ref<string>('general')
const loadingProfiles = ref(true)
const profileError = ref('')
const copiedBlock = ref<'quick' | null>(null)
let copyResetTimer: ReturnType<typeof setTimeout> | null = null

const quickStartExample = String.raw`title=彩云追月（片段）
instrument=erhu
1=G
4/4
tempo=88

\mp (5 6 7 1') | h2' h1' | 5~ 6 7 ~5 | (3 2 3 1,) |
L: 彩 云 追 月 夜 色 浓 山 河 醉

tempo=72
\f q[1+3+5] 5. 6 5 | $1 2 3$ 5 6 7 | ^>3 ^>2 1 7, | h6. q6 q5 |
L: 一 曲 霓 裳 舞 半 空 天 上 仙

\ff (6 5 4 3) | 2 3 4 5~ | 5 6 7 1' | 6 7 1' 2' |
L: 醉 倒 了 月 下 人 不 知 归 路

\p $6 5 6$ 3 5 4 | 1=D (^.) 2 3 4 5 | (^r) (^f) 1, 2 3 5 | w1 |
L: 且 将 此 曲 寄 相 思 千 里 共 婵 娟`

const docSections: DocSection[] = [
  {
    id: 'quick-start',
    label: '快速开始',
    icon: FlashOutline,
  },
  {
    id: 'metadata',
    label: '谱面信息',
    icon: InformationCircleOutline,
  },
  {
    id: 'notes',
    label: '音符与八度',
    icon: MusicalNotesOutline,
  },
  {
    id: 'duration',
    label: '时值与连音',
    icon: TimerOutline,
  },
  {
    id: 'measures',
    label: '和弦与小节',
    icon: AppsOutline,
  },
  {
    id: 'expression',
    label: '力度、歌词与注释',
    icon: CreateOutline,
  },
  {
    id: 'performance-marks',
    label: '演奏技巧',
    icon: ColorWandOutline,
  },
  {
    id: 'quick-reference',
    label: '速查表',
    icon: ListOutline,
  },
]

const syntaxSections: SyntaxSection[] = [
  {
    id: 'metadata',
    title: '谱面信息',
    kicker: '文档设置',
    entries: [
      { syntax: '1=C', name: '调号', description: '以 C 为大调主音。' },
      { syntax: '4/4', name: '拍号', description: '每小节四拍，以四分音符为一拍。' },
      { syntax: '1=G', name: '中途转调', description: '写在小节音符之前，后续小节转为 G 调；不能写在音符之后。' },
      { syntax: '3/4', name: '中途变拍', description: '写在小节音符之前，后续小节转为 3/4 拍。' },
      { syntax: 'title=名称', name: '谱名', description: '可选，显示在谱面顶部。' },
      {
        syntax: 'instrument=erhu',
        name: '乐器模式',
        description: '可使用 general、erhu、ruan 或 guzheng；zhongruan 作为 ruan 的别名同样可用。',
        keywords: ['普通', '二胡', '阮', '古筝', '中阮', 'zhongruan'],
      },
      { syntax: 'tempo=120', name: '速度', description: '20–300 的整数 BPM；省略时按 120 播放。' },
      { syntax: 'tempo=80', name: '中途变速', description: '独占一行写在目标小节第一个音符之前，对该小节及后续小节生效。' },
    ],
  },
  {
    id: 'notes',
    title: '音符与八度',
    kicker: '音高',
    entries: [
      { syntax: '1–7', name: '音级', description: '分别表示 do 到 si。' },
      { syntax: '0', name: '休止符', description: '占据时值但不发声。' },
      { syntax: "1'  2'", name: '高八度', description: '在数字后加撇号，谱面显示上加点。' },
      { syntax: '1,  2,', name: '低八度', description: '在数字后加逗号，谱面显示下加点。' },
      { syntax: '#1  b7', name: '升降半音', description: '在音级前写升号或降号，也可后置（如 1#、7b）。' },
      { syntax: 'x4  bb7', name: '重升重降', description: '分别升高或降低两个半音，可前置或后置。' },
      { syntax: 'n4  ♮4', name: '还原号', description: '取消之前的升降，只能前置。' },
      { syntax: 'qs1  qf2', name: '四分之一升/降', description: '微音程，升高或降低半个半音，只能前置。' },
      { syntax: 'tqs3  tqf4', name: '四分之三升/降', description: '微音程，升高或降低一个半半音，只能前置。' },
    ],
  },
  {
    id: 'duration',
    title: '时值与连音',
    kicker: '节奏',
    entries: [
      { syntax: 'w1', name: '全音符', description: '持续 4 拍。' },
      { syntax: 'h1', name: '二分音符', description: '持续 2 拍。' },
      { syntax: '1', name: '四分音符', description: '持续 1 拍，也是默认时值。' },
      { syntax: 'q1', name: '八分音符', description: '持续 1/2 拍。' },
      { syntax: 's1', name: '十六分音符', description: '持续 1/4 拍。' },
      { syntax: 'd1', name: '三十二分音符', description: '持续 1/8 拍。' },
      { syntax: 'dd1', name: '六十四分音符', description: '持续 1/16 拍。' },
      { syntax: 'ddd1  dddd1  ddddd1', name: '更短时值', description: '持续 1/32、1/64、1/128 拍，每多一个 d 缩短一半。' },
      { syntax: '5.', name: '附点', description: '将原时值延长一半；必须写在音级之后，不能写在时值前缀与音级之间。' },
      { syntax: '1-  /  1--', name: '延长线', description: '每个减号延长一拍，可叠加。' },
      { syntax: '5~  /  ~5', name: '延音线', description: '5~ 标记起点（音符后），~5 标记终点（音符前）；跨小节时下一小节首音自动成为终点。' },
      { syntax: '$123$', name: '三连音', description: '紧凑写法，组内三个音总共占 1 拍。' },
      { syntax: '$1 2 3$', name: '空格分隔连音组', description: '与紧凑写法等价。' },
      { syntax: '$1234$', name: '四连音', description: '组内四个音总共占 1 拍。' },
      { syntax: '$3:2;s1 s2$', name: '显式连音比例', description: '用 实际数:常规数; 指定比例，适用于组内时值无法推导比例的情况。' },
      { syntax: '(1 2', name: '连音线', description: '在前一个音前写 ( 标记起点，在后一个音后写 ) 标记终点；可跨小节。' },
    ],
  },
  {
    id: 'measures',
    title: '和弦与小节',
    kicker: '结构',
    entries: [
      { syntax: '[1+3+5]', name: '和弦', description: '多个音高同时发声，并在谱面上纵向排列。' },
      { syntax: 'q[1+3+5]', name: '带时值和弦', description: '这个和弦持续 1/2 拍。' },
      { syntax: '|', name: '小节线', description: '结束当前小节。' },
      { syntax: '||', name: '双小节线', description: '与 | 等效；渲染时最后一小节自动显示终止线。' },
      { syntax: '|:  :|', name: '反复记号', description: '分别表示反复段落的起点和终点。' },
      { syntax: '*2', name: '重复小节', description: '当前内容重复 2 次，小节号相应增加。' },
      { syntax: '*10', name: '多次重复', description: '当前内容重复 10 次。' },
    ],
  },
  {
    id: 'expression',
    title: '力度、歌词与注释',
    kicker: '文本与表现',
    entries: [
      { syntax: '\\pppp  \\ppp  \\pp  \\p', name: '弱力度', description: '从极弱到弱，p 为基本弱。' },
      { syntax: '\\mp  \\mf', name: '中弱与中强', description: '表示介于弱和强之间的力度。' },
      { syntax: '\\f  \\ff  \\fff  \\ffff', name: '强力度', description: '从强到极强，f 为基本强。' },
      { syntax: '\\fp  \\sfz  \\sfp', name: '强后弱与突强', description: '强后弱、突强、突强后弱。' },
      { syntax: '\\sf  \\fz  \\rfz', name: '强调类力度', description: '突强、强调、加强。' },
      {
        syntax: '^.  ^>  ^-',
        name: '断奏、重音、保持',
        description: '分别表示 staccato、accent、tenuto。',
      },
      {
        syntax: '^r  ^f',
        name: '颤音、延音',
        description: '颤音 trill、延音记号 fermata。',
      },
      {
        syntax: '^l',
        name: '颤弓/轮指/摇指',
        description: 'tremolo（三道斜线），仅 erhu/ruan/guzheng 可用。',
        keywords: ['颤弓', '轮指', '摇指', 'tremolo'],
      },
      {
        syntax: '^lh',
        name: '连线滑音',
        description: '写在目标音前，连接前一个音；古筝模式自动判断上滑或下滑。',
        keywords: ['滑音', 'continuous-slide', 'slide'],
      },
      {
        syntax: '(^l)  (^.)  (^>)  (^r)  (^f)',
        name: '小节级简写',
        description: '写在小节开头，对该小节所有音符与和弦生效，休止符不继承。',
      },
      {
        syntax: 'L: 春 风 又 绿',
        name: '歌词行',
        description: '按音符顺序一一匹配，休止符不分配歌词。',
      },
      { syntax: '// 注释内容', name: '注释', description: '从双斜线开始忽略到当前行末尾。' },
    ],
  },
]

const quickReferenceEntries: SyntaxEntry[] = [
  { syntax: '1–7 / 0', name: '音级 / 休止符', description: '数字直接输入。' },
  { syntax: "' / ,", name: '高 / 低八度', description: '写在音级数字后，可叠加。' },
  { syntax: '# / b / x / bb / n', name: '变音', description: '升、降、重升、重降、还原（可前置或后置；还原仅前缀）。' },
  { syntax: 'qs / qf / tqs / tqf', name: '微音程', description: '四分之一升/降、四分之三升/降（仅前缀）。' },
  { syntax: 'w / h / q / s / d / dd', name: '时值前缀', description: '全、二分、四分、八分、十六分、三十二分、六十四分音符。' },
  { syntax: '. / -', name: '附点 / 延长线', description: '附点延长一半（写在音级后），- 每个延长一拍。' },
  { syntax: '5~ / ~5', name: '延音线', description: '起点（音符后）/ 终点（音符前），跨小节自动传播。' },
  { syntax: '( / )', name: '连音线', description: '前缀 ( 标记起点，后缀 ) 标记终点。' },
  { syntax: '$...$ / *N', name: '连音组 / 重复', description: '$ 包裹连音组（紧凑或空格分隔），*N 重复当前小节 N 次。' },
  { syntax: '$3:2;...$', name: '显式连音比例', description: '实际数:常规数; 指定比例。' },
  { syntax: '[a+b]', name: '和弦', description: '方括号内 + 分隔，可加时值前缀。' },
  { syntax: '| / || / |: :|', name: '小节结构', description: '小节线、双小节线、反复记号。' },
  { syntax: '\\p / \\f / \\sfz 等', name: '力度', description: '16 种力度标记，\\ 加符号。' },
  { syntax: '^. / ^> / ^r 等', name: '演奏法', description: '断奏、重音、颤音等，^ 加标记。' },
  { syntax: '^l / ^lh', name: '民乐标记', description: '颤弓/轮指/摇指（^l）、连线滑音（^lh），仅 erhu/ruan/guzheng。' },
  { syntax: '(^...)', name: '小节级标记', description: '括号包裹，写在小节开头。' },
  { syntax: 'instrument=...', name: '乐器模式', description: '普通、二胡、阮或古筝（zhongruan 同 ruan）。' },
  { syntax: 'L: / //', name: '歌词 / 注释', description: '歌词单独成行，注释忽略到行尾。' },
  { syntax: '// @part / // @page', name: '分谱 / 分页', description: '多声部或多页输入标记。' },
]

const activeMeta = computed(
  () => docSections.find((section) => section.id === activeSection.value) ?? docSections[0],
)

const activeTableSection = computed(
  () => syntaxSections.find((section) => section.id === activeSection.value) ?? null,
)

const normalizedQuery = computed(() => normalizeText(searchQuery.value))

const orderedProfiles = computed(() => {
  const order = ['general', 'erhu', 'ruan', 'zhongruan', 'guzheng']
  return [...profiles.value].sort(
    (left, right) => order.indexOf(left.id) - order.indexOf(right.id),
  )
})

const searchGroups = computed<SearchGroup[]>(() => {
  if (!normalizedQuery.value) return []

  const items: SearchItem[] = [
    {
      key: 'quick-start-example',
      groupKey: 'quick-start',
      groupTitle: '快速开始',
      sectionId: 'quick-start',
      sectionTitle: '快速开始',
      syntax: 'title=彩云追月（片段） …',
      name: '快速开始示例',
      description: '包含力度、连音线、延音线、和弦、连音组、附点、演奏法、移调八度、中途转调、乐器模式和歌词。',
      keywords: [quickStartExample],
    },
    ...syntaxSections.flatMap((section) =>
      section.entries.map((entry) => ({
        key: `${section.id}-${entry.syntax}`,
        groupKey: section.id,
        groupTitle: section.title,
        sectionId: section.id,
        sectionTitle: section.title,
        syntax: entry.syntax,
        name: entry.name,
        description: entry.description,
        keywords: entry.keywords ?? [],
      })),
    ),
    ...orderedProfiles.value.flatMap((profile) => {
      const groupKey = `profile-${profile.id}`
      const sectionTitle = `${profile.name}演奏技巧`
      const marks: SearchItem[] = (profile.marks ?? []).map((mark) => ({
        key: `${groupKey}-${mark.id}`,
        groupKey,
        groupTitle: sectionTitle,
        sectionId: 'performance-marks',
        sectionTitle,
        syntax: mark.syntax,
        name: mark.name,
        description: mark.description,
        keywords: [mark.category, mark.placement, mark.target ?? ''],
        profileId: profile.id,
      }))
      const rangeExamples: SearchItem[] = (profile.range_examples ?? []).map((example, index) => ({
        key: `${groupKey}-range-${index}`,
        groupKey,
        groupTitle: sectionTitle,
        sectionId: 'performance-marks',
        sectionTitle,
        syntax: example.syntax,
        name: '范围写法',
        description: example.description,
        keywords: ['范围', '整小节'],
        profileId: profile.id,
      }))
      const combinationExamples: SearchItem[] = (profile.combination_examples ?? []).map(
        (example, index) => ({
          key: `${groupKey}-combination-${index}`,
          groupKey,
          groupTitle: sectionTitle,
          sectionId: 'performance-marks',
          sectionTitle,
          syntax: example.syntax,
          name: '组合示例',
          description: example.description,
          keywords: ['组合'],
          profileId: profile.id,
        }),
      )
      return [...marks, ...rangeExamples, ...combinationExamples]
    }),
  ]

  const matchingItems = items.filter((item) =>
    normalizeText([
      item.syntax,
      item.name,
      item.description,
      item.sectionTitle,
      ...item.keywords,
    ].join(' ')).includes(normalizedQuery.value),
  )

  const groups = new Map<string, SearchGroup>()
  for (const item of matchingItems) {
    const group = groups.get(item.groupKey)
    if (group) {
      group.items.push(item)
    } else {
      groups.set(item.groupKey, {
        key: item.groupKey,
        title: item.groupTitle,
        items: [item],
      })
    }
  }
  return [...groups.values()]
})

const searchResultCount = computed(() =>
  searchGroups.value.reduce((total, group) => total + group.items.length, 0),
)

onMounted(() => {
  void loadProfiles()
})

onBeforeUnmount(() => {
  if (copyResetTimer) clearTimeout(copyResetTimer)
})

function normalizeText(value: string): string {
  return value.trim().toLocaleLowerCase('zh-CN')
}

function profileIdForText(profileId: string): string {
  return profileId === 'zhongruan' ? 'ruan' : profileId
}

async function loadProfiles(): Promise<void> {
  loadingProfiles.value = true
  profileError.value = ''
  try {
    profiles.value = await requireData(notationApi.listInstrumentProfiles())
    const preferredProfile = profiles.value.find(
      (profile) => profileIdForText(profile.id) === 'general',
    )
    if (!profiles.value.some((profile) => profile.id === activeProfile.value)) {
      activeProfile.value = preferredProfile?.id ?? profiles.value[0]?.id ?? 'general'
    }
  } catch {
    profileError.value = '请确认后端服务正在运行后重试。'
  } finally {
    loadingProfiles.value = false
  }
}

function openSearchResult(item: SearchItem): void {
  if (item.profileId) activeProfile.value = item.profileId
  activeSection.value = item.sectionId
  searchQuery.value = ''
}

async function copyExample(block: 'quick', content: string): Promise<void> {
  try {
    await window.navigator.clipboard.writeText(content)
    copiedBlock.value = block
    message.success('示例已复制')
    if (copyResetTimer) clearTimeout(copyResetTimer)
    copyResetTimer = setTimeout(() => {
      copiedBlock.value = null
    }, 1600)
  } catch {
    message.error('复制失败，请稍后重试')
  }
}
</script>

<style scoped>
.syntax-main {
  grid-template-rows: auto minmax(0, 1fr);
}

.syntax-search {
  width: min(280px, 100%);
  flex-shrink: 0;
}

.syntax-section {
  min-width: 0;
}

.table-wrap {
  width: 100%;
  overflow-x: auto;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.syntax-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 14px;
}

.syntax-table th {
  padding: 9px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-base);
  color: var(--text-tertiary);
  font-size: 13px;
  font-weight: 650;
  text-align: left;
}

.syntax-table th:first-child,
.syntax-table td:first-child {
  width: 30%;
}

.syntax-table th:nth-child(2),
.syntax-table td:nth-child(2) {
  width: 24%;
}

.syntax-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-light);
  color: var(--text-secondary);
  line-height: 1.55;
  vertical-align: top;
}

.syntax-table tr:last-child td {
  border-bottom: 0;
}

.syntax-table tbody tr {
  transition: background 0.12s ease;
}

.syntax-table tbody tr:hover {
  background: var(--accent-light);
}

.syntax-table td:nth-child(2) {
  color: var(--text-primary);
  font-weight: 600;
}

code {
  font-family: 'Cascadia Code', 'Consolas', monospace;
}

.syntax-table code,
.profile-meta code,
.example-row code,
.result-row code {
  display: inline-block;
  max-width: 100%;
  padding: 2px 5px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.code-block {
  overflow: hidden;
  border: 1px solid #2b3039;
  border-radius: 7px;
  background: #1b1f27;
  color: #e9edf2;
}

:global(.theme-dark) .code-block {
  border-color: #292d35;
  background: #0e1014;
}

.code-toolbar {
  display: flex;
  min-height: 34px;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 0 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  color: #9ea6b2;
  font-size: 13px;
}

.copy-button {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: #c8ced7;
  cursor: pointer;
  transition:
    color 0.15s ease,
    background 0.15s ease,
    transform 0.1s ease;
}

.copy-button:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.copy-button:active {
  transform: scale(0.96);
}

.copy-button :deep(svg) {
  width: 15px;
  height: 15px;
}

.code-block pre {
  margin: 0;
  padding: 15px 17px 18px;
  overflow-x: auto;
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.code-block pre code {
  font: inherit;
}

.profile-loading {
  display: grid;
  gap: 14px;
  padding: 12px 0;
}

.inline-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.inline-state strong {
  font-size: 15px;
}

.inline-state p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 14px;
}

.profile-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 2px 0 14px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.profile-examples {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 28px;
  margin-top: 24px;
}

.example-list h3,
.result-group h4 {
  margin: 0 0 10px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 650;
}

.example-row {
  display: grid;
  grid-template-columns: minmax(100px, 36%) minmax(0, 1fr);
  gap: 12px;
  padding: 9px 0;
  border-top: 1px solid var(--border-light);
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.55;
}

.profile-table th:first-child,
.profile-table td:first-child {
  width: 25%;
}

.profile-table th:nth-child(2),
.profile-table td:nth-child(2) {
  width: 25%;
}

.syntax-search-results {
  padding-top: 4px;
}

.syntax-search-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
}

.syntax-search-kicker {
  margin: 0 0 6px;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.syntax-search-header h3 {
  margin: 0;
  font-size: 21px;
  font-weight: 680;
  line-height: 1.35;
}

.result-group {
  padding: 24px 0 6px;
}

.result-list {
  border-top: 1px solid var(--border);
}

.result-row {
  display: grid;
  width: 100%;
  grid-template-columns: minmax(130px, 25%) minmax(0, 1fr) minmax(90px, 18%);
  align-items: start;
  gap: 16px;
  padding: 12px;
  border: 0;
  border-bottom: 1px solid var(--border-light);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.result-row:hover {
  background: var(--accent-light);
}

.result-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.result-copy strong {
  font-size: 14px;
  font-weight: 650;
}

.result-copy span,
.result-section {
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.5;
}

.result-section {
  text-align: right;
}

.result-row:focus-visible,
.copy-button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

:deep(.n-tabs-nav) {
  margin-bottom: 12px;
}

:deep(.n-tabs-tab) {
  font-size: 14px;
}

:deep(.n-button__content),
:deep(.n-base-selection-label) {
  font-size: 14px;
}

:deep(.n-empty) {
  padding: 32px 0;
}

@media (max-width: 820px) {
  .syntax-page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }

  .syntax-search {
    max-width: none;
  }

  .profile-examples {
    grid-template-columns: 1fr;
    gap: 22px;
  }

  .result-row {
    grid-template-columns: minmax(100px, 34%) minmax(0, 1fr);
    gap: 10px;
  }

  .result-section {
    display: none;
  }

  .syntax-search-header {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 620px) {
  .syntax-table {
    font-size: 13.5px;
  }

  .syntax-table th,
  .syntax-table td {
    padding: 8px;
  }

  .syntax-table th:first-child,
  .syntax-table td:first-child {
    width: 34%;
  }

  .syntax-table th:nth-child(2),
  .syntax-table td:nth-child(2) {
    width: 25%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .copy-button,
  .syntax-table tbody tr,
  .result-row {
    transition: none;
  }
}
</style>
