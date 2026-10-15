<template>
  <div class="settings-view">
    <aside
      class="sv-sidebar"
      :aria-label="t('syntax.sectionNavLabel')"
    >
      <div class="sv-sidebar-header">
        <span class="sv-sidebar-eyebrow">{{ t('syntax.eyebrow') }}</span>
        <h2>{{ t('syntax.heading') }}</h2>
      </div>

      <nav class="sv-category-list">
        <button
          v-for="section in docSections"
          :key="section.id"
          type="button"
          :class="['sv-category-button', { active: activeSection === section.id }]"
          :aria-current="activeSection === section.id ? 'page' : undefined"
          @click="selectSection(section.id)"
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
          :placeholder="t('syntax.searchPlaceholder')"
          :aria-label="t('syntax.searchAriaLabel')"
        >
          <template #prefix>
            <n-icon :component="SearchOutline" />
          </template>
        </n-input>
      </header>

      <div
        ref="bodyRef"
        class="sv-page-body"
      >
        <div class="sv-panel-container">
          <div
            v-if="normalizedQuery"
            class="syntax-search-results"
            aria-live="polite"
          >
            <div class="syntax-search-header">
              <div>
                <p class="syntax-search-kicker">
                  {{ t('syntax.search.kicker') }}
                </p>
                <h3>{{ t('syntax.search.resultCount', { count: searchResultCount }) }}</h3>
              </div>
              <n-button
                size="small"
                quaternary
                @click="searchQuery = ''"
              >
                {{ t('syntax.search.clear') }}
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
                    <code><syntax-highlight-text
                      :text="item.syntax"
                      :query="normalizedQuery"
                    /></code>
                    <span class="result-copy">
                      <strong><syntax-highlight-text
                        :text="item.name"
                        :query="normalizedQuery"
                      /></strong>
                      <span><syntax-highlight-text
                        :text="item.description"
                        :query="normalizedQuery"
                      /></span>
                    </span>
                    <span class="result-section">{{ item.sectionTitle }}</span>
                  </button>
                </div>
              </section>
            </template>

            <n-empty
              v-else
              :description="t('syntax.search.empty')"
            >
              <template #extra>
                <n-button
                  size="small"
                  @click="searchQuery = ''"
                >
                  {{ t('syntax.search.backToFull') }}
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
              <div
                class="code-block"
                data-search-key="quick-start-example"
                :class="{ 'block-highlight': isHighlighted('quick-start-example') }"
              >
                <div class="code-toolbar">
                  <span>{{ t('syntax.codeBlock.notation') }}</span>
                  <n-tooltip>
                    <template #trigger>
                      <button
                        type="button"
                        class="copy-button"
                        :aria-label="copiedBlock === 'quick' ? t('syntax.codeBlock.copied') : t('syntax.codeBlock.copy')"
                        @click="copyExample('quick', quickStartExample)"
                      >
                        <n-icon :component="copiedBlock === 'quick' ? CheckmarkOutline : CopyOutline" />
                      </button>
                    </template>
                    {{ copiedBlock === 'quick' ? t('syntax.codeBlock.copied') : t('syntax.codeBlock.copy') }}
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
                      <th>{{ t('syntax.table.syntax') }}</th>
                      <th>{{ t('syntax.table.meaning') }}</th>
                      <th>{{ t('syntax.table.descOrExample') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="entry in activeTableSection.entries"
                      :key="`${activeTableSection.id}-${entry.syntax}`"
                      :data-search-key="`${activeTableSection.id}-${entry.syntax}`"
                      :class="{ 'row-highlight': isHighlighted(`${activeTableSection.id}-${entry.syntax}`) }"
                    >
                      <td><code>{{ entry.syntax }}</code></td>
                      <td>{{ entry.name }}</td>
                      <td>{{ entry.description }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div
                v-if="activeSection === 'lyrics'"
                class="lyric-examples"
              >
                <div
                  v-for="example in lyricExamples"
                  :key="example.key"
                >
                  <h3>{{ example.title }}</h3>
                  <div
                    class="code-block"
                    :data-search-key="example.key"
                    :class="{ 'block-highlight': isHighlighted(example.key) }"
                  >
                    <div class="code-toolbar">
                      <span>{{ t('syntax.codeBlock.notation') }}</span>
                      <n-tooltip>
                        <template #trigger>
                          <button
                            type="button"
                            class="copy-button"
                            :aria-label="copiedBlock === example.key ? t('syntax.codeBlock.copied') : t('syntax.codeBlock.copy')"
                            @click="copyExample(example.key, example.content)"
                          >
                            <n-icon :component="copiedBlock === example.key ? CheckmarkOutline : CopyOutline" />
                          </button>
                        </template>
                        {{ copiedBlock === example.key ? t('syntax.codeBlock.copied') : t('syntax.codeBlock.copy') }}
                      </n-tooltip>
                    </div>
                    <pre><code>{{ example.content }}</code></pre>
                  </div>
                </div>
              </div>
            </section>

            <section
              v-else-if="activeSection === 'performance-marks'"
              class="syntax-section"
            >
              <div
                v-if="loadingProfiles"
                class="profile-loading"
                :aria-label="t('syntax.profiles.loading')"
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
                  <strong>{{ t('syntax.profiles.errorTitle') }}</strong>
                  <p>{{ profileError }}</p>
                </div>
                <n-button
                  size="small"
                  secondary
                  :loading="loadingProfiles"
                  @click="loadProfiles"
                >
                  {{ t('syntax.profiles.retry') }}
                </n-button>
              </div>

              <n-empty
                v-else-if="!orderedProfiles.length"
                :description="t('syntax.profiles.empty')"
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
                    <span>{{ t('syntax.profiles.meta') }}</span>
                    <code>instrument={{ profileIdForText(profile.id) }}</code>
                  </div>

                  <div
                    v-if="profile.marks?.length"
                    class="table-wrap"
                  >
                    <table class="syntax-table profile-table">
                      <thead>
                        <tr>
                          <th>{{ t('syntax.table.syntax') }}</th>
                          <th>{{ t('syntax.table.technique') }}</th>
                          <th>{{ t('syntax.table.notationNote') }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="mark in profile.marks"
                          :key="mark.id"
                          :data-search-key="`profile-${profile.id}-${mark.id}`"
                          :class="{ 'row-highlight': isHighlighted(`profile-${profile.id}-${mark.id}`) }"
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
                    :description="t('syntax.profiles.noTechnique')"
                  />

                  <div
                    v-if="profile.range_examples?.length || profile.combination_examples?.length"
                    class="profile-examples"
                  >
                    <div
                      v-if="profile.range_examples?.length"
                      class="example-list"
                    >
                      <h3>{{ t('syntax.profiles.range') }}</h3>
                      <div
                        v-for="(example, index) in profile.range_examples"
                        :key="`range-${example.syntax}`"
                        :data-search-key="`profile-${profile.id}-range-${index}`"
                        :class="['example-row', { 'row-highlight': isHighlighted(`profile-${profile.id}-range-${index}`) }]"
                      >
                        <code>{{ example.syntax }}</code>
                        <span>{{ example.description }}</span>
                      </div>
                    </div>
                    <div
                      v-if="profile.combination_examples?.length"
                      class="example-list"
                    >
                      <h3>{{ t('syntax.profiles.combination') }}</h3>
                      <div
                        v-for="(example, index) in profile.combination_examples"
                        :key="`combination-${example.syntax}`"
                        :data-search-key="`profile-${profile.id}-combination-${index}`"
                        :class="['example-row', { 'row-highlight': isHighlighted(`profile-${profile.id}-combination-${index}`) }]"
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
                      <th>{{ t('syntax.table.syntax') }}</th>
                      <th>{{ t('syntax.table.meaning') }}</th>
                      <th>{{ t('syntax.table.note') }}</th>
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
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
  TextOutline,
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
import SyntaxHighlightText from '../components/SyntaxHighlightText.vue'
import { t } from '../i18n'
import type { InstrumentProfileCatalog } from '../models/types'

type SectionId =
  | 'quick-start'
  | 'metadata'
  | 'notes'
  | 'duration'
  | 'measures'
  | 'expression'
  | 'lyrics'
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
const bodyRef = ref<HTMLElement | null>(null)
const searchQuery = ref('')
const highlightKey = ref('')
let highlightTimer: ReturnType<typeof setTimeout> | null = null
let frameHandle: number | null = null
const activeSection = ref<SectionId>('quick-start')
const profiles = ref<InstrumentProfileCatalog[]>([])
const activeProfile = ref<string>('general')
const loadingProfiles = ref(true)
const profileError = ref('')
const copiedBlock = ref<string | null>(null)
let copyResetTimer: ReturnType<typeof setTimeout> | null = null

const quickStartExample = String.raw`// @page 1 name="bach_invention_04_bwv775_a4_page_001.png"
// @part 1 name="Piano(staff 1)"
title=Invention4
tempo=120
1=F
3/8
s6, s7, s1 s2 s3 s4 |
s#5, s4 s3 s2 s1 s7, |
q1 q3 q6 |
q2 q#5 q7 |
s6 s7 s1' s2' s3' s4' |
s#5 s4' s3' s2' s1' s7 |
s1' s6 s7 s1' s2' s3' |
s4 s3' s2' s1' s7 s6 |
s7 s5 s6 s7 s1' s2' |
s3 s2' s1' s7 s6 s5 |
s6 s7 s1' s6 s7 s1' |
q2 q0 q0 |
s5 s6 s7 s5 s6 s7 |
q1 q0 q4~ |
~q4 q3 q2 |
s5 s4 s3 s2 s1 s7, |
s1 s2 q2. s1 |
q1 q5 q5 |
^sc 5. |
5. |
5. |
s5 s4 s3 s2 s1 s7, |
s5 s6, s7, s#1 s2 s3 |
s4 s3 s2 s1 s7, s6, |
s4 s5, s6, s7, s1 s2 |
s3 sn4 s5 s6 s7 s1' |
s#2 s1' s7 s6 s5 sn4 |
s5 sn4 s6 s5 sn4 s3 |
s#2 s3 s#2 s#1 s7, s6, |
s5, s6, s7, s#1 s#2 s3 |
s6, s5 sn4 s3 s#2 s#1 |
s7, s#1 s#2 s3 sn4 s5 |
s#1 s7 s6 s5 sn4 s3 |
s#2 s3 sn4 s5 s6 s7 |
s3 s1' s7 s6 s5 sn4 |
s3' s#2' s#1' s7 q3'~ |
~s3' s6 qn4. s3 |
q3. s3 s4 s5 |
0. |
s4 s2 s3 s4 s5 s6 |
// @part 2 name="Piano(staff 2)"
1=F
3/8
0. |
0. |
s6,, s7,, s1, s2, s3, s4, |
s#5,, s4, s3, s2, s1, s7,, |
q1, q3, q6, |
q7,, q2, q#5, |
q6,, q6, q1, |
q2, q3, q4, |
q5,, q5, q7,, |
q1, q2, q3, |
s4, s2, s3, s4, s5, s6, |
s7,, s6, s5, s4, s3, s2, |
s3, s1, s2, s3, s4, s5, |
s6,, s5, s4, s3, s2, s1, |
s7,, s5,, s6,, s7,, s1, s2, |
s3,, s2, s1, s7,, s6,, s5,, |
s6,, s4,, q5,, q5,,, |
s1,, s2,, s3,, s4,, s5,, s6,, |
s7,,, s6,, s5,, s4,, s3,, s2,, |
s3,, s4,, s5,, s6,, s7,, s1, |
s2,, s1, s7,, s6,, s5,, s4,, |
s3,, s4,, s5,, s3,, s4,, s5,, |
q#1,, q0 q0 |
s2,, s3,, s4,, s2,, s3,, s4,, |
q7,,, q0 q0 |
q1,, q1, q6,, |
qn4,, q#2,, q7,,, |
s3,, s#2,, s3,, sn4,, s5,, s6,, |
^sc 7,,. |
7,,. |
^> 7,,. |
7,,. |
^. 7,,. |
q7,, q7, q6, |
q5, qn4, q3, |
q6, q7, q1 |
q6, \p q7, \pp q7,, |
s3, ^. s3,, s4,, s5,, s6,, sb7,, |
h[3,,+1,,] |
q2,,. s2,, s3,, s4,, |
// @page 2 name="bach_invention_04_bwv775_a4_page_002.png"
// @part 1 name="Piano"
1=F
3/8
s7, s6 s5 s4 s3 s2 |
q3 s1' s7 q1' |
q2 q7 q0 |
s6 s7 s1' s2' s3' s4' |
s#5 s4' s3' s2' s1' s7 |
q1' q6 q2~ |
~s2 s6 s5 s7 s3 s5 |
s6 sn4 q#5. s6 |
s6 sn5 s4 s3 s2 s1 |
s4 s#5, s6, s7, s1 s2 |
s3 s6 q1 s7, s6, |
^f 6,. |
// @part 2 name="Piano"
tempo=120
1=F
3/8
q3, q7, q3 |
s6 s7 s1' sn2' s#3' sn4' |
s5 sn4' s#3' sn2' s1' s7 |
q6 q1' qn4' |
q5 q7 q#3' |
sn4 s5 s6 s7 s1' s2' |
s#3 s2' s1' s7 s6 s5 |
s6 s7 q1' q1 |
q2. s3 s2 s1 |
s7, s2' s1' s7 s6 s5 |
s6 s7 q1' q1 |
^f n4,. |`

const lyricBasicExample = String.raw`1=C
4/4
1 1 5 5 | 6 6 h5 |
/L: 一 闪 一 闪 | 亮 晶 晶/`

const lyricStreamsExample = String.raw`1=C
4/4
1 1 5 5 | 6 6 h5 | 4 4 3 3 | 2 2 h1 |
/L: 一 闪 一 闪 & Twinkle twinkle |
    亮 晶 晶 & little star |
    满 天 都 是 & Up above the |
    小 星 星 & world so high/`

interface LyricExample {
  key: string
  title: string
  content: string
}

const lyricExamples = computed<LyricExample[]>(() => [
  { key: 'lyrics-example-basic', title: t('syntax.lyricExamples.basic'), content: lyricBasicExample },
  { key: 'lyrics-example-streams', title: t('syntax.lyricExamples.streams'), content: lyricStreamsExample },
])

const docSections = computed<DocSection[]>(() => [
  {
    id: 'quick-start',
    label: t('syntax.section.quickStart'),
    icon: FlashOutline,
  },
  {
    id: 'metadata',
    label: t('syntax.section.metadata'),
    icon: InformationCircleOutline,
  },
  {
    id: 'notes',
    label: t('syntax.section.notes'),
    icon: MusicalNotesOutline,
  },
  {
    id: 'duration',
    label: t('syntax.section.duration'),
    icon: TimerOutline,
  },
  {
    id: 'measures',
    label: t('syntax.section.measures'),
    icon: AppsOutline,
  },
  {
    id: 'expression',
    label: t('syntax.section.expression'),
    icon: CreateOutline,
  },
  {
    id: 'lyrics',
    label: t('syntax.section.lyrics'),
    icon: TextOutline,
  },
  {
    id: 'performance-marks',
    label: t('syntax.section.performanceMarks'),
    icon: ColorWandOutline,
  },
  {
    id: 'quick-reference',
    label: t('syntax.section.quickReference'),
    icon: ListOutline,
  },
])

const syntaxSections = computed<SyntaxSection[]>(() => [
  {
    id: 'metadata',
    title: t('syntax.sections.metadata.title'),
    kicker: t('syntax.sections.metadata.kicker'),
    entries: [
      { syntax: '1=C', name: t('syntax.entries.metadata.keySignature.name'), description: t('syntax.entries.metadata.keySignature.desc') },
      { syntax: '4/4', name: t('syntax.entries.metadata.timeSignature.name'), description: t('syntax.entries.metadata.timeSignature.desc') },
      { syntax: '1=G', name: t('syntax.entries.metadata.midwayKeyChange.name'), description: t('syntax.entries.metadata.midwayKeyChange.desc') },
      { syntax: '3/4', name: t('syntax.entries.metadata.midwayMeterChange.name'), description: t('syntax.entries.metadata.midwayMeterChange.desc') },
      { syntax: 'title=Name', name: t('syntax.entries.metadata.title.name'), description: t('syntax.entries.metadata.title.desc') },
      {
        syntax: 'instrument=erhu',
        name: t('syntax.entries.metadata.instrument.name'),
        description: t('syntax.entries.metadata.instrument.desc'),
        keywords: ['普通', '二胡', '阮', '古筝', '中阮', 'zhongruan'],
      },
      { syntax: 'tempo=120', name: t('syntax.entries.metadata.tempo.name'), description: t('syntax.entries.metadata.tempo.desc') },
      { syntax: 'tempo=80', name: t('syntax.entries.metadata.midwayTempo.name'), description: t('syntax.entries.metadata.midwayTempo.desc') },
    ],
  },
  {
    id: 'notes',
    title: t('syntax.sections.notes.title'),
    kicker: t('syntax.sections.notes.kicker'),
    entries: [
      { syntax: '1–7', name: t('syntax.entries.notes.scaleDegree.name'), description: t('syntax.entries.notes.scaleDegree.desc') },
      { syntax: '0', name: t('syntax.entries.notes.rest.name'), description: t('syntax.entries.notes.rest.desc') },
      { syntax: "1'  2'", name: t('syntax.entries.notes.octaveUp.name'), description: t('syntax.entries.notes.octaveUp.desc') },
      { syntax: '1,  2,', name: t('syntax.entries.notes.octaveDown.name'), description: t('syntax.entries.notes.octaveDown.desc') },
      { syntax: '#1  b7', name: t('syntax.entries.notes.accidentalSharpFlat.name'), description: t('syntax.entries.notes.accidentalSharpFlat.desc') },
      { syntax: 'x4  bb7', name: t('syntax.entries.notes.doubleAccidental.name'), description: t('syntax.entries.notes.doubleAccidental.desc') },
      { syntax: 'n4  ♮4', name: t('syntax.entries.notes.natural.name'), description: t('syntax.entries.notes.natural.desc') },
      { syntax: 'qs1  qf2', name: t('syntax.entries.notes.quarterAccidental.name'), description: t('syntax.entries.notes.quarterAccidental.desc') },
      { syntax: 'tqs3  tqf4', name: t('syntax.entries.notes.threeQuarterAccidental.name'), description: t('syntax.entries.notes.threeQuarterAccidental.desc') },
    ],
  },
  {
    id: 'duration',
    title: t('syntax.sections.duration.title'),
    kicker: t('syntax.sections.duration.kicker'),
    entries: [
      { syntax: 'w1', name: t('syntax.entries.duration.whole.name'), description: t('syntax.entries.duration.whole.desc') },
      { syntax: 'h1', name: t('syntax.entries.duration.half.name'), description: t('syntax.entries.duration.half.desc') },
      { syntax: '1', name: t('syntax.entries.duration.quarter.name'), description: t('syntax.entries.duration.quarter.desc') },
      { syntax: 'q1', name: t('syntax.entries.duration.eighth.name'), description: t('syntax.entries.duration.eighth.desc') },
      { syntax: 's1', name: t('syntax.entries.duration.sixteenth.name'), description: t('syntax.entries.duration.sixteenth.desc') },
      { syntax: 'd1', name: t('syntax.entries.duration.thirtySecond.name'), description: t('syntax.entries.duration.thirtySecond.desc') },
      { syntax: 'dd1', name: t('syntax.entries.duration.sixtyFourth.name'), description: t('syntax.entries.duration.sixtyFourth.desc') },
      { syntax: 'ddd1  dddd1  ddddd1', name: t('syntax.entries.duration.shorter.name'), description: t('syntax.entries.duration.shorter.desc') },
      { syntax: '5.', name: t('syntax.entries.duration.dotted.name'), description: t('syntax.entries.duration.dotted.desc') },
      { syntax: '1-  /  1--', name: t('syntax.entries.duration.fermata.name'), description: t('syntax.entries.duration.fermata.desc') },
      { syntax: '5~  /  ~5', name: t('syntax.entries.duration.tie.name'), description: t('syntax.entries.duration.tie.desc') },
      { syntax: '$123$', name: t('syntax.entries.duration.triplet.name'), description: t('syntax.entries.duration.triplet.desc') },
      { syntax: '$1 2 3$', name: t('syntax.entries.duration.tripletSpaced.name'), description: t('syntax.entries.duration.tripletSpaced.desc') },
      { syntax: '$1234$', name: t('syntax.entries.duration.quadruplet.name'), description: t('syntax.entries.duration.quadruplet.desc') },
      { syntax: '$3:2;s1 s2$', name: t('syntax.entries.duration.explicitRatio.name'), description: t('syntax.entries.duration.explicitRatio.desc') },
      { syntax: '(1 2', name: t('syntax.entries.duration.slur.name'), description: t('syntax.entries.duration.slur.desc') },
    ],
  },
  {
    id: 'measures',
    title: t('syntax.sections.measures.title'),
    kicker: t('syntax.sections.measures.kicker'),
    entries: [
      { syntax: '[1+3+5]', name: t('syntax.entries.measures.chord.name'), description: t('syntax.entries.measures.chord.desc') },
      { syntax: 'q[1+3+5]', name: t('syntax.entries.measures.chordDuration.name'), description: t('syntax.entries.measures.chordDuration.desc') },
      { syntax: '|', name: t('syntax.entries.measures.barline.name'), description: t('syntax.entries.measures.barline.desc') },
      { syntax: '||', name: t('syntax.entries.measures.doubleBarline.name'), description: t('syntax.entries.measures.doubleBarline.desc') },
      { syntax: '|:  :|', name: t('syntax.entries.measures.repeat.name'), description: t('syntax.entries.measures.repeat.desc') },
      { syntax: '*2', name: t('syntax.entries.measures.repeatBar.name'), description: t('syntax.entries.measures.repeatBar.desc') },
      { syntax: '*10', name: t('syntax.entries.measures.multiRepeat.name'), description: t('syntax.entries.measures.multiRepeat.desc') },
      {
        syntax: '&',
        name: t('syntax.entries.measures.voice.name'),
        description: t('syntax.entries.measures.voice.desc'),
        keywords: ['复调', '声线', '多声部', 'voice', 'polyphony', 'lane'],
      },
    ],
  },
  {
    id: 'expression',
    title: t('syntax.sections.expression.title'),
    kicker: t('syntax.sections.expression.kicker'),
    entries: [
      { syntax: '\\pppp  \\ppp  \\pp  \\p', name: t('syntax.entries.expression.ppp.name'), description: t('syntax.entries.expression.ppp.desc') },
      { syntax: '\\mp  \\mf', name: t('syntax.entries.expression.mpMf.name'), description: t('syntax.entries.expression.mpMf.desc') },
      { syntax: '\\f  \\ff  \\fff  \\ffff', name: t('syntax.entries.expression.ff.name'), description: t('syntax.entries.expression.ff.desc') },
      { syntax: '\\fp  \\sfz  \\sfp', name: t('syntax.entries.expression.fpSfz.name'), description: t('syntax.entries.expression.fpSfz.desc') },
      { syntax: '\\sf  \\fz  \\rfz', name: t('syntax.entries.expression.sfFz.name'), description: t('syntax.entries.expression.sfFz.desc') },
      {
        syntax: '^.  ^>  ^-',
        name: t('syntax.entries.expression.staccatoAccentTenuto.name'),
        description: t('syntax.entries.expression.staccatoAccentTenuto.desc'),
      },
      {
        syntax: '^r  ^f',
        name: t('syntax.entries.expression.trillFermata.name'),
        description: t('syntax.entries.expression.trillFermata.desc'),
      },
      {
        syntax: '^l',
        name: t('syntax.entries.expression.tremolo.name'),
        description: t('syntax.entries.expression.tremolo.desc'),
        keywords: ['颤弓', '轮指', '摇指', 'tremolo'],
      },
      {
        syntax: '^lh',
        name: t('syntax.entries.expression.slide.name'),
        description: t('syntax.entries.expression.slide.desc'),
        keywords: ['滑音', 'continuous-slide', 'slide'],
      },
      {
        syntax: '(^l)  (^.)  (^>)  (^r)  (^f)',
        name: t('syntax.entries.expression.measureLevelShorthand.name'),
        description: t('syntax.entries.expression.measureLevelShorthand.desc'),
      },
      { syntax: '// comment', name: t('syntax.entries.expression.comment.name'), description: t('syntax.entries.expression.comment.desc') },
    ],
  },
  {
    id: 'lyrics',
    title: t('syntax.sections.lyrics.title'),
    kicker: t('syntax.sections.lyrics.kicker'),
    entries: [
      {
        syntax: '/L: 一 闪 一 闪 | 亮 晶 晶/',
        name: t('syntax.entries.lyrics.block.name'),
        description: t('syntax.entries.lyrics.block.desc'),
        keywords: ['歌词', '歌词块', 'lyric', '/L:'],
      },
      {
        syntax: '一 闪 一 闪 & Twinkle twinkle',
        name: t('syntax.entries.lyrics.streams.name'),
        description: t('syntax.entries.lyrics.streams.desc'),
        keywords: ['歌词流', '分段歌词', '多段歌词', 'verse', 'stream'],
      },
      {
        syntax: 'q眠  s闪  d哒  h长  w远',
        name: t('syntax.entries.lyrics.duration.name'),
        description: t('syntax.entries.lyrics.duration.desc'),
        keywords: ['歌词时值', 'duration prefix'],
      },
      {
        syntax: 'q0',
        name: t('syntax.entries.lyrics.placeholder.name'),
        description: t('syntax.entries.lyrics.placeholder.desc'),
        keywords: ['占位', 'placeholder'],
      },
      {
        syntax: '/L: 一 闪 一 闪 | ↵ 亮 晶 晶/',
        name: t('syntax.entries.lyrics.multiLine.name'),
        description: t('syntax.entries.lyrics.multiLine.desc'),
        keywords: ['多行歌词', '换行', 'multi-line'],
      },
    ],
  },
])

const quickReferenceEntries = computed<SyntaxEntry[]>(() => [
  { syntax: '1–7 / 0', name: t('syntax.quickRef.scale.name'), description: t('syntax.quickRef.scale.desc') },
  { syntax: "' / ,", name: t('syntax.quickRef.octave.name'), description: t('syntax.quickRef.octave.desc') },
  { syntax: '# / b / x / bb / n', name: t('syntax.quickRef.accidental.name'), description: t('syntax.quickRef.accidental.desc') },
  { syntax: 'qs / qf / tqs / tqf', name: t('syntax.quickRef.microtone.name'), description: t('syntax.quickRef.microtone.desc') },
  { syntax: 'w / h / q / s / d / dd', name: t('syntax.quickRef.durationPrefix.name'), description: t('syntax.quickRef.durationPrefix.desc') },
  { syntax: '. / -', name: t('syntax.quickRef.dotExtend.name'), description: t('syntax.quickRef.dotExtend.desc') },
  { syntax: '5~ / ~5', name: t('syntax.quickRef.tie.name'), description: t('syntax.quickRef.tie.desc') },
  { syntax: '( / )', name: t('syntax.quickRef.slur.name'), description: t('syntax.quickRef.slur.desc') },
  { syntax: '$...$ / *N', name: t('syntax.quickRef.groupRepeat.name'), description: t('syntax.quickRef.groupRepeat.desc') },
  { syntax: '$3:2;...$', name: t('syntax.quickRef.explicitRatio.name'), description: t('syntax.quickRef.explicitRatio.desc') },
  { syntax: '[a+b]', name: t('syntax.quickRef.chord.name'), description: t('syntax.quickRef.chord.desc') },
  { syntax: '| / || / |: :|', name: t('syntax.quickRef.barStructure.name'), description: t('syntax.quickRef.barStructure.desc') },
  { syntax: '&', name: t('syntax.quickRef.voice.name'), description: t('syntax.quickRef.voice.desc') },
  { syntax: '\\p / \\f / \\sfz etc.', name: t('syntax.quickRef.dynamics.name'), description: t('syntax.quickRef.dynamics.desc') },
  { syntax: '^. / ^> / ^r etc.', name: t('syntax.quickRef.articulation.name'), description: t('syntax.quickRef.articulation.desc') },
  { syntax: '^l / ^lh', name: t('syntax.quickRef.folk.name'), description: t('syntax.quickRef.folk.desc') },
  { syntax: '(^...)', name: t('syntax.quickRef.measureLevel.name'), description: t('syntax.quickRef.measureLevel.desc') },
  { syntax: 'instrument=...', name: t('syntax.quickRef.instrument.name'), description: t('syntax.quickRef.instrument.desc') },
  { syntax: '/L: .../', name: t('syntax.quickRef.lyricComment.name'), description: t('syntax.quickRef.lyricComment.desc') },
  { syntax: '// @part / // @page', name: t('syntax.quickRef.partPage.name'), description: t('syntax.quickRef.partPage.desc') },
])

const activeMeta = computed(
  () => docSections.value.find((section) => section.id === activeSection.value) ?? docSections.value[0],
)

const activeTableSection = computed(
  () => syntaxSections.value.find((section) => section.id === activeSection.value) ?? null,
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
      groupTitle: t('syntax.quickStartExample.groupTitle'),
      sectionId: 'quick-start',
      sectionTitle: t('syntax.quickStartExample.sectionTitle'),
      syntax: 'title=Invention4 …',
      name: t('syntax.quickStartExample.name'),
      description: t('syntax.quickStartExample.description'),
      keywords: [quickStartExample],
    },
    ...lyricExamples.value.map((example) => ({
      key: example.key,
      groupKey: 'lyrics',
      groupTitle: t('syntax.sections.lyrics.title'),
      sectionId: 'lyrics' as SectionId,
      sectionTitle: t('syntax.sections.lyrics.title'),
      syntax: '/L: …/',
      name: example.title,
      description: example.title,
      keywords: [example.content, '歌词', 'lyric'],
    })),
    ...syntaxSections.value.flatMap((section) =>
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
      const sectionTitle = `${profile.name}${t('syntax.profiles.techniquesSuffix')}`
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
        name: t('syntax.profiles.range'),
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
          name: t('syntax.profiles.combination'),
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
  clearHighlight()
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
    profileError.value = t('syntax.profiles.error')
  } finally {
    loadingProfiles.value = false
  }
}

function clearHighlight(): void {
  if (highlightTimer) {
    clearTimeout(highlightTimer)
    highlightTimer = null
  }
  if (frameHandle !== null) {
    window.cancelAnimationFrame(frameHandle)
    frameHandle = null
  }
  highlightKey.value = ''
}

function scheduleHighlightClear(): void {
  if (highlightTimer) clearTimeout(highlightTimer)
  highlightTimer = setTimeout(() => {
    highlightTimer = null
    highlightKey.value = ''
  }, 2600)
}

function isHighlighted(key: string): boolean {
  return highlightKey.value === key
}

function scrollBodyToTop(): void {
  bodyRef.value?.scrollTo({ top: 0 })
}

function selectSection(sectionId: SectionId): void {
  clearHighlight()
  activeSection.value = sectionId
  searchQuery.value = ''
  scrollBodyToTop()
}

function nextFrameAsync(): Promise<void> {
  return new Promise((resolve) => {
    frameHandle = window.requestAnimationFrame(() => {
      frameHandle = null
      resolve()
    })
  })
}

function findTargetElement(key: string): HTMLElement | null {
  const body = bodyRef.value
  if (!body || !key) return null
  // 不使用 CSS 属性选择器：item.key 含 \ $ ( ) 等字符，反斜杠会被当作转义符
  for (const node of Array.from(body.querySelectorAll<HTMLElement>('[data-search-key]'))) {
    if (node.dataset.searchKey === key) return node
  }
  return null
}

async function waitForTarget(key: string, maxFrames: number): Promise<HTMLElement | null> {
  for (let attempt = 0; attempt < maxFrames; attempt += 1) {
    const existing = findTargetElement(key)
    if (existing) return existing
    await nextFrameAsync()
  }
  return findTargetElement(key)
}

async function revealSearchTarget(key: string, needsLazyRender: boolean): Promise<void> {
  await nextTick()
  // 演奏技巧区的标签面板是懒渲染的且带切换动画，需要轮询等待其出现在 DOM 中
  const target = await waitForTarget(key, needsLazyRender ? 12 : 2)
  if (!target) {
    scrollBodyToTop()
    scheduleHighlightClear()
    return
  }
  target.scrollIntoView({ block: 'center', behavior: 'smooth' })
  scheduleHighlightClear()
}

async function openSearchResult(item: SearchItem): Promise<void> {
  // 重复点击同一项时先渲染一帧（移除高亮类），保证动画能够重播
  const repeated = highlightKey.value === item.key
  clearHighlight()
  if (repeated) await nextTick()

  if (item.profileId) activeProfile.value = item.profileId
  activeSection.value = item.sectionId
  highlightKey.value = item.key
  searchQuery.value = ''
  await revealSearchTarget(item.key, item.sectionId === 'performance-marks')
}


async function copyExample(block: string, content: string): Promise<void> {
  try {
    await window.navigator.clipboard.writeText(content)
    copiedBlock.value = block
    message.success(t('syntax.message.exampleCopied'))
    if (copyResetTimer) clearTimeout(copyResetTimer)
    copyResetTimer = setTimeout(() => {
      copiedBlock.value = null
    }, 1600)
  } catch {
    message.error(t('syntax.message.copyFailed'))
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

.lyric-examples {
  display: grid;
  gap: 20px;
  margin-top: 24px;
}

.example-list h3,
.lyric-examples h3,
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

@keyframes row-flash {
  0%,
  55% {
    background-color: var(--accent-light);
  }
  100% {
    background-color: transparent;
  }
}

@keyframes block-flash {
  0%,
  55% {
    box-shadow: 0 0 0 3px var(--accent-light);
  }
  100% {
    box-shadow: none;
  }
}

.syntax-table tbody tr.row-highlight td {
  animation: row-flash 2.4s ease-out forwards;
}

.syntax-table tbody tr.row-highlight td:first-child,
.example-row.row-highlight {
  box-shadow: inset 3px 0 0 var(--accent);
}

.example-row.row-highlight {
  animation: row-flash 2.4s ease-out forwards;
}

.code-block.block-highlight {
  animation: block-flash 2.4s ease-out forwards;
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

  /* 关闭动画但保留静态高亮，直到定时器清除 */
  .syntax-table tbody tr.row-highlight td,
  .example-row.row-highlight {
    animation: none;
    background-color: var(--accent-light);
  }

  .code-block.block-highlight {
    animation: none;
    box-shadow: 0 0 0 3px var(--accent-light);
  }
}
</style>
