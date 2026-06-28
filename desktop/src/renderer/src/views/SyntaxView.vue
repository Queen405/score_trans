<template>
  <div
    ref="scrollRoot"
    class="syntax-view"
    @scroll.passive="handleScroll"
  >
    <div class="syntax-page">
      <header class="syntax-header">
        <div class="header-copy">
          <p class="eyebrow">
            REFERENCE
          </p>
          <h1>简谱语法</h1>
          <p>使用纯文本描述音符、节奏和演奏技巧，并渲染为简谱谱面。</p>
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

      <div class="mobile-section-select">
        <label for="syntax-section-select">章节</label>
        <n-select
          id="syntax-section-select"
          :value="activeSection"
          :options="sectionOptions"
          @update:value="handleSectionSelect"
        />
      </div>

      <div class="syntax-layout">
        <aside class="syntax-toc">
          <p class="toc-title">
            本页内容
          </p>
          <nav aria-label="语法章节">
            <button
              v-for="section in sectionLinks"
              :key="section.id"
              type="button"
              :class="{ active: activeSection === section.id }"
              @click="scrollToSection(section.id)"
            >
              {{ section.title }}
            </button>
          </nav>
        </aside>

        <main class="syntax-content">
          <div
            v-if="normalizedQuery"
            class="search-results"
            aria-live="polite"
          >
            <div class="search-results-header">
              <div>
                <p class="section-kicker">
                  搜索结果
                </p>
                <h2>找到 {{ searchResultCount }} 条相关语法</h2>
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
                <h3>{{ group.title }}</h3>
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

          <template v-else>
            <section
              id="quick-start"
              class="doc-section first-section"
            >
              <div class="section-heading">
                <p class="section-kicker">
                  入门
                </p>
                <h2>快速开始</h2>
                <p>谱面信息写在开头，空一行后按从左到右的顺序输入音符和小节线。</p>
              </div>
              <div class="code-block">
                <div class="code-toolbar">
                  <span>简谱文本</span>
                  <n-tooltip>
                    <template #trigger>
                      <button
                        type="button"
                        class="copy-button"
                        :aria-label="copiedBlock === 'quick' ? '已复制快速开始示例' : '复制快速开始示例'"
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
              v-for="section in syntaxSections"
              :id="section.id"
              :key="section.id"
              class="doc-section"
            >
              <div class="section-heading">
                <p class="section-kicker">
                  {{ section.kicker }}
                </p>
                <h2>{{ section.title }}</h2>
                <p>{{ section.summary }}</p>
              </div>
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
                      v-for="entry in section.entries"
                      :key="`${section.id}-${entry.syntax}`"
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
              id="performance-marks"
              class="doc-section"
            >
              <div class="section-heading">
                <p class="section-kicker">
                  演奏法
                </p>
                <h2>分乐器演奏技巧</h2>
                <p>同一个记谱图形只定义一次，具体名称和演奏解释由乐器模式决定。</p>
              </div>

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
              id="complete-example"
              class="doc-section"
            >
              <div class="section-heading">
                <p class="section-kicker">
                  示例
                </p>
                <h2>完整示例</h2>
                <p>这个片段组合了谱面信息、力度、连音线、延音线和歌词。</p>
              </div>
              <div class="code-block">
                <div class="code-toolbar">
                  <span>练习曲.jianpu</span>
                  <n-tooltip>
                    <template #trigger>
                      <button
                        type="button"
                        class="copy-button"
                        :aria-label="copiedBlock === 'complete' ? '已复制完整示例' : '复制完整示例'"
                        @click="copyExample('complete', completeExample)"
                      >
                        <n-icon :component="copiedBlock === 'complete' ? CheckmarkOutline : CopyOutline" />
                      </button>
                    </template>
                    {{ copiedBlock === 'complete' ? '已复制' : '复制示例' }}
                  </n-tooltip>
                </div>
                <pre><code>{{ completeExample }}</code></pre>
              </div>
            </section>

            <section
              id="quick-reference"
              class="doc-section"
            >
              <div class="section-heading">
                <p class="section-kicker">
                  REFERENCE
                </p>
                <h2>速查表</h2>
                <p>编辑时最常用的输入形式，完整说明以前文章节为准。</p>
              </div>
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
          </template>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  CheckmarkOutline,
  CopyOutline,
  SearchOutline,
} from '@vicons/ionicons5'
import {
  NButton,
  NEmpty,
  NIcon,
  NInput,
  NSelect,
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
  | 'complete-example'
  | 'quick-reference'

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
  summary: string
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

const props = withDefaults(defineProps<{ active?: boolean }>(), {
  active: false,
})

const message = useMessage()
const scrollRoot = ref<HTMLElement | null>(null)
const searchQuery = ref('')
const activeSection = ref<SectionId>('quick-start')
const profiles = ref<InstrumentProfileCatalog[]>([])
const activeProfile = ref<string>('general')
const loadingProfiles = ref(true)
const profileError = ref('')
const copiedBlock = ref<'quick' | 'complete' | null>(null)
let scrollFrame = 0
let copyResetTimer: ReturnType<typeof setTimeout> | null = null

const quickStartExample = `title=小星星
1=C
4/4
tempo=100

1 1 5 5 | 6 6 h5 | 4 4 3 3 | 2 2 h1 |
L: 一 闪 一 闪 亮 晶 晶`

const completeExample = String.raw`title=练习曲
1=G
4/4

\mf 1 2 3 4 | q5 q5 q3 q1 q5 q5 q3 q1 | h2. q3 q4 | w1 |
L: 春 眠 不 觉 晓 处 处 闻 啼 鸟 飞 飞 飞 去 去 去

\p (5 6 5 4) | 3 2 1 ~1 | 2 3 4 3 | h2 h0 |
L: 夜 来 风 雨 声 花 落 知 多 少 安 睡 吧`

const syntaxSections: SyntaxSection[] = [
  {
    id: 'metadata',
    title: '谱面信息',
    kicker: '文档设置',
    summary: '调号和拍号是必需信息，其余字段可按需要写在乐谱开头。',
    entries: [
      { syntax: '1=C', name: '调号', description: '以 C 为大调主音。' },
      { syntax: '4/4', name: '拍号', description: '每小节四拍，以四分音符为一拍。' },
      { syntax: '1=G', name: '中途转调', description: '写在小节前，后续小节转为 G 调。' },
      { syntax: '3/4', name: '中途变拍', description: '写在小节前，后续小节转为 3/4 拍。' },
      { syntax: 'title=名称', name: '谱名', description: '可选，显示在谱面顶部。' },
      {
        syntax: 'instrument=erhu',
        name: '乐器模式',
        description: '可使用 general、erhu、ruan 或 guzheng。',
        keywords: ['普通', '二胡', '阮', '古筝'],
      },
      { syntax: 'tempo=120', name: '速度', description: '可选，以 BPM 表示。' },
    ],
  },
  {
    id: 'notes',
    title: '音符与八度',
    kicker: '音高',
    summary: '数字表示音级，撇号、逗号和变音前缀改变音符的实际音高。',
    entries: [
      { syntax: '1–7', name: '音级', description: '分别表示 do 到 si。' },
      { syntax: '0', name: '休止符', description: '占据时值但不发声。' },
      { syntax: "1'  2'", name: '高八度', description: '在数字后加撇号，谱面显示上加点。' },
      { syntax: '1,  2,', name: '低八度', description: '在数字后加逗号，谱面显示下加点。' },
      { syntax: '#1  b7', name: '升降半音', description: '在音级前写升号或降号。' },
      { syntax: 'x4  bb7', name: '重升重降', description: '分别升高或降低两个半音。' },
    ],
  },
  {
    id: 'duration',
    title: '时值与连音',
    kicker: '节奏',
    summary: '时值前缀控制音符长度，附点、延音线和连音组用于补充节奏关系。',
    entries: [
      { syntax: 'w1', name: '全音符', description: '持续 4 拍。' },
      { syntax: 'h1', name: '二分音符', description: '持续 2 拍。' },
      { syntax: '1', name: '四分音符', description: '持续 1 拍，也是默认时值。' },
      { syntax: 'q1', name: '八分音符', description: '持续 1/2 拍。' },
      { syntax: 's1', name: '十六分音符', description: '持续 1/4 拍。' },
      { syntax: 'd1', name: '三十二分音符', description: '持续 1/8 拍。' },
      { syntax: '5.', name: '附点', description: '将原时值延长一半。' },
      { syntax: '5~  /  ~5', name: '延音线', description: '分别标记延音线的起点和终点。' },
      { syntax: '$123$', name: '三连音', description: '组内三个音总共占 1 拍。' },
      { syntax: '$1234$', name: '四连音', description: '组内四个音总共占 1 拍。' },
      { syntax: '(1 2)', name: '连音线', description: '将范围内的音符连接为圆滑奏。' },
    ],
  },
  {
    id: 'measures',
    title: '和弦与小节',
    kicker: '结构',
    summary: '方括号组织同时发声的音，小节线和重复记号组织乐谱结构。',
    entries: [
      { syntax: '[1+3+5]', name: '和弦', description: '多个音高同时发声，并在谱面上纵向排列。' },
      { syntax: 'q[1+3+5]', name: '带时值和弦', description: '这个和弦持续 1/2 拍。' },
      { syntax: '|', name: '小节线', description: '结束当前小节。' },
      { syntax: '||', name: '终止线', description: '结束整首乐谱。' },
      { syntax: '|:  :|', name: '反复记号', description: '分别表示反复段落的起点和终点。' },
      { syntax: '*2', name: '重复小节', description: '当前内容重复 2 次，小节号相应增加。' },
      { syntax: '*10', name: '多次重复', description: '当前内容重复 10 次。' },
    ],
  },
  {
    id: 'expression',
    title: '力度、歌词与注释',
    kicker: '文本与表现',
    summary: '力度标记跟随音符，歌词按有效音符顺序匹配，注释不会进入谱面。',
    entries: [
      { syntax: '\\p  \\f', name: '弱与强', description: '在后续音符前写入基础力度。' },
      { syntax: '\\mp  \\mf', name: '中弱与中强', description: '表示介于弱和强之间的力度。' },
      { syntax: '\\ff  \\sfz', name: '很强与突强', description: '用于更强或突然强调的力度。' },
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
  { syntax: "' / ,", name: '高 / 低八度', description: '写在音级数字后。' },
  { syntax: '# / b / x / bb', name: '变音', description: '升、降、重升、重降。' },
  { syntax: 'q / s / d', name: '短时值', description: '八、十六、三十二分音符。' },
  { syntax: 'h / w', name: '长时值', description: '二分音符、全音符。' },
  { syntax: '. / ~', name: '附点 / 延音线', description: '附点写在音后，延音线标记起止。' },
  { syntax: '( ) / [a+b]', name: '连音线 / 和弦', description: '圆括号表示范围，方括号表示同时发声。' },
  { syntax: '| / || / |: :|', name: '小节结构', description: '小节线、终止线、反复记号。' },
  { syntax: '*N', name: '重复', description: '将当前小节重复 N 次。' },
  { syntax: 'instrument=...', name: '乐器模式', description: '普通、二胡、阮或古筝。' },
  { syntax: 'L: / //', name: '歌词 / 注释', description: '歌词单独成行，注释忽略到行尾。' },
]

const sectionLinks: Array<{ id: SectionId; title: string }> = [
  { id: 'quick-start', title: '快速开始' },
  { id: 'metadata', title: '谱面信息' },
  { id: 'notes', title: '音符与八度' },
  { id: 'duration', title: '时值与连音' },
  { id: 'measures', title: '和弦与小节' },
  { id: 'expression', title: '力度、歌词与注释' },
  { id: 'performance-marks', title: '演奏技巧' },
  { id: 'complete-example', title: '完整示例' },
  { id: 'quick-reference', title: '速查表' },
]

const sectionOptions = sectionLinks.map((section) => ({
  label: section.title,
  value: section.id,
}))

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
      syntax: 'title=小星星 …',
      name: '快速开始示例',
      description: '包含谱名、调号、拍号、速度、音符、小节线和歌词。',
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
    {
      key: 'complete-example',
      groupKey: 'complete-example',
      groupTitle: '完整示例',
      sectionId: 'complete-example',
      sectionTitle: '完整示例',
      syntax: 'title=练习曲 …',
      name: '完整简谱示例',
      description: '包含力度、连音线、延音线、歌词和多种时值。',
      keywords: [completeExample],
    },
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

watch(
  () => props.active,
  (active) => {
    if (active) nextTick(updateActiveSection)
  },
)

onMounted(() => {
  void loadProfiles()
  nextTick(updateActiveSection)
})

onBeforeUnmount(() => {
  if (scrollFrame) window.cancelAnimationFrame(scrollFrame)
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

function handleScroll(): void {
  if (scrollFrame || normalizedQuery.value) return
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = 0
    updateActiveSection()
  })
}

function updateActiveSection(): void {
  const root = scrollRoot.value
  if (!root || normalizedQuery.value) return

  const rootTop = root.getBoundingClientRect().top
  const headerHeight =
    root.querySelector<HTMLElement>('.syntax-header')?.offsetHeight ?? 0
  const activationOffset = headerHeight + 36
  let current: SectionId = sectionLinks[0].id
  for (const section of sectionLinks) {
    const element = root.querySelector<HTMLElement>(`#${section.id}`)
    if (
      element &&
      element.getBoundingClientRect().top - rootTop <= activationOffset
    ) {
      current = section.id
    } else {
      break
    }
  }
  activeSection.value = current
}

function handleSectionSelect(value: string): void {
  void scrollToSection(value as SectionId)
}

async function scrollToSection(sectionId: SectionId): Promise<void> {
  searchQuery.value = ''
  await nextTick()

  const root = scrollRoot.value
  const target = root?.querySelector<HTMLElement>(`#${sectionId}`)
  if (!root || !target) return

  const headerHeight =
    root.querySelector<HTMLElement>('.syntax-header')?.offsetHeight ?? 0
  const top =
    target.getBoundingClientRect().top -
    root.getBoundingClientRect().top +
    root.scrollTop -
    headerHeight -
    18
  root.scrollTo({ top, behavior: 'smooth' })
  activeSection.value = sectionId
}

async function openSearchResult(item: SearchItem): Promise<void> {
  if (item.profileId) activeProfile.value = item.profileId
  await scrollToSection(item.sectionId)
}

async function copyExample(block: 'quick' | 'complete', content: string): Promise<void> {
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
.syntax-view {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  color: var(--text-primary);
  font-size: 15px;
}

.syntax-page {
  width: 100%;
  margin: 0;
  padding: 0 0 48px;
}

.syntax-header {
  position: sticky;
  z-index: 20;
  top: 0;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  padding: 14px 0 22px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}

.header-copy {
  min-width: 0;
}

.eyebrow,
.section-kicker {
  margin: 0 0 6px;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.syntax-header h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 680;
  line-height: 1.25;
  letter-spacing: 0;
}

.syntax-header p:last-child {
  margin: 7px 0 0;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.6;
}

.syntax-search {
  width: min(520px, 42vw);
  flex: 0 1 520px;
}

.syntax-search :deep(.n-input__input-el) {
  font-size: 15px;
}

.syntax-layout {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 40px;
}

.syntax-toc {
  position: sticky;
  top: 120px;
  align-self: start;
  padding-top: 32px;
}

.toc-title {
  margin: 0 0 10px;
  padding-left: 12px;
  color: var(--text-tertiary);
  font-size: 13px;
  font-weight: 650;
}

.syntax-toc nav {
  display: flex;
  flex-direction: column;
}

.syntax-toc button {
  position: relative;
  width: 100%;
  padding: 7px 12px;
  border: 0;
  border-left: 2px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  font-size: 14px;
  line-height: 1.35;
  text-align: left;
  cursor: pointer;
  transition:
    color 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease;
}

.syntax-toc button:hover {
  background: var(--accent-light);
  color: var(--text-primary);
}

.syntax-toc button.active {
  border-left-color: var(--accent);
  color: var(--accent);
  font-weight: 650;
}

.syntax-toc button:focus-visible,
.copy-button:focus-visible,
.result-row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.mobile-section-select {
  display: none;
}

.syntax-content {
  min-width: 0;
}

.doc-section {
  scroll-margin-top: 20px;
  padding: 34px 0 38px;
  border-top: 1px solid var(--border);
}

.doc-section.first-section {
  border-top: 0;
}

.section-heading {
  max-width: 78ch;
  margin-bottom: 18px;
}

.section-heading h2,
.search-results-header h2 {
  margin: 0;
  font-size: 21px;
  font-weight: 680;
  line-height: 1.35;
  letter-spacing: 0;
}

.section-heading > p:last-child {
  margin: 7px 0 0;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.65;
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
.result-group h3 {
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

.search-results {
  padding: 34px 0 48px;
}

.search-results-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
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

@media (max-width: 900px) {
  .syntax-header {
    align-items: stretch;
    flex-direction: column;
    gap: 16px;
  }

  .syntax-search {
    width: min(520px, 100%);
    flex-basis: auto;
  }

  .mobile-section-select {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    padding: 16px 0 2px;
  }

  .mobile-section-select label {
    color: var(--text-tertiary);
    font-size: 14px;
    font-weight: 650;
  }

  .syntax-layout {
    display: block;
    max-width: none;
  }

  .syntax-toc {
    display: none;
  }
}

@media (max-width: 620px) {
  .syntax-page {
    padding-bottom: 32px;
  }

  .doc-section {
    padding: 28px 0 32px;
  }

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

  .search-results-header {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .syntax-toc button,
  .copy-button,
  .syntax-table tbody tr,
  .result-row {
    transition: none;
  }
}
</style>
