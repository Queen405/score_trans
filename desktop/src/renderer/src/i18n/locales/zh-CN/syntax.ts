const syntax = {
  // 侧边栏 / 页头
  eyebrow: '语法参考',
  heading: '语法说明',
  searchPlaceholder: '搜索语法、名称或说明',
  sectionNavLabel: '语法章节',
  searchAriaLabel: '搜索简谱语法',

  // 章节导航
  section: {
    quickStart: '快速开始',
    metadata: '谱面信息',
    notes: '音符与八度',
    duration: '时值与连音',
    measures: '和弦与小节',
    expression: '力度与注释',
    lyrics: '歌词',
    performanceMarks: '演奏技巧',
    quickReference: '速查表',
  },

  // 搜索结果
  search: {
    kicker: '搜索结果',
    resultCount: '找到 {count} 条相关语法',
    clear: '清除搜索',
    empty: '没有找到匹配的语法',
    backToFull: '返回完整说明',
  },

  // 代码块
  codeBlock: {
    notation: '简谱文本',
    copied: '已复制',
    copy: '复制示例',
  },

  // 表格表头
  table: {
    syntax: '语法',
    meaning: '含义',
    descOrExample: '说明或示例',
    note: '备注',
    technique: '技巧',
    notationNote: '记谱说明',
  },

  // 演奏技巧（运行时数据）
  profiles: {
    loading: '正在加载演奏技巧',
    errorTitle: '演奏技巧暂时无法加载',
    retry: '重新加载',
    empty: '当前没有可用的乐器语法',
    meta: '谱面元数据',
    noTechnique: '该模式没有专属演奏技巧',
    range: '范围写法',
    combination: '组合示例',
    techniquesSuffix: '演奏技巧',
    error: '请确认后端服务正在运行后重试。',
  },

  // 语法段落标题与副标题
  sections: {
    metadata: { title: '谱面信息', kicker: '文档设置' },
    notes: { title: '音符与八度', kicker: '音高' },
    duration: { title: '时值与连音', kicker: '节奏' },
    measures: { title: '和弦与小节', kicker: '结构' },
    expression: { title: '力度与注释', kicker: '文本与表现' },
    lyrics: { title: '歌词', kicker: '填词与对齐' },
  },

  // 快速开始搜索项
  quickStartExample: {
    groupTitle: '快速开始',
    sectionTitle: '快速开始',
    name: '快速开始示例',
    description:
      '巴赫二部创意曲，包含多页（@page）、多声部（@part）、调号、拍号、速度、附点、延音线、力度与演奏法标记。',
  },

  // 歌词章节示例标题
  lyricExamples: {
    basic: '基础对齐',
    streams: '多段歌词与多行书写',
  },

  // 语法段落条目
  entries: {
    metadata: {
      keySignature: { name: '调号', desc: '以 C 为大调主音。' },
      timeSignature: { name: '拍号', desc: '每小节四拍，以四分音符为一拍。' },
      midwayKeyChange: {
        name: '中途转调',
        desc: '写在小节音符之前，后续小节转为 G 调；不能写在音符之后。',
      },
      midwayMeterChange: {
        name: '中途变拍',
        desc: '写在小节音符之前，后续小节转为 3/4 拍。',
      },
      title: { name: '谱名', desc: '可选，显示在谱面顶部。' },
      instrument: {
        name: '乐器模式',
        desc: '可使用 general、erhu、ruan 或 guzheng；zhongruan 作为 ruan 的别名同样可用。',
      },
      tempo: { name: '速度', desc: '20–300 的整数 BPM；省略时按 120 播放。' },
      midwayTempo: {
        name: '中途变速',
        desc: '独占一行写在目标小节第一个音符之前，对该小节及后续小节生效。',
      },
    },
    notes: {
      scaleDegree: { name: '音级', desc: '分别表示 do 到 si。' },
      rest: { name: '休止符', desc: '占据时值但不发声。' },
      octaveUp: { name: '高八度', desc: '在数字后加撇号，谱面显示上加点。' },
      octaveDown: { name: '低八度', desc: '在数字后加逗号，谱面显示下加点。' },
      accidentalSharpFlat: {
        name: '升降半音',
        desc: '在音级前写升号或降号，也可后置（如 1#、7b）。',
      },
      doubleAccidental: {
        name: '重升重降',
        desc: '分别升高或降低两个半音，可前置或后置。',
      },
      natural: { name: '还原号', desc: '取消之前的升降，只能前置。' },
      quarterAccidental: {
        name: '四分之一升/降',
        desc: '微音程，升高或降低半个半音，只能前置。',
      },
      threeQuarterAccidental: {
        name: '四分之三升/降',
        desc: '微音程，升高或降低一个半半音，只能前置。',
      },
    },
    duration: {
      whole: { name: '全音符', desc: '持续 4 拍。' },
      half: { name: '二分音符', desc: '持续 2 拍。' },
      quarter: { name: '四分音符', desc: '持续 1 拍，也是默认时值。' },
      eighth: { name: '八分音符', desc: '持续 1/2 拍。' },
      sixteenth: { name: '十六分音符', desc: '持续 1/4 拍。' },
      thirtySecond: { name: '三十二分音符', desc: '持续 1/8 拍。' },
      sixtyFourth: { name: '六十四分音符', desc: '持续 1/16 拍。' },
      shorter: {
        name: '更短时值',
        desc: '持续 1/32、1/64、1/128 拍，每多一个 d 缩短一半。',
      },
      dotted: {
        name: '附点',
        desc: '将原时值延长一半；必须写在音级之后，不能写在时值前缀与音级之间。',
      },
      fermata: { name: '延长线', desc: '每个减号延长一拍，可叠加。' },
      tie: {
        name: '延音线',
        desc: '5~ 标记起点（音符后），~5 标记终点（音符前）；跨小节时下一小节首音自动成为终点。',
      },
      triplet: { name: '三连音', desc: '紧凑写法，组内三个音总共占 1 拍。' },
      tripletSpaced: {
        name: '空格分隔连音组',
        desc: '与紧凑写法等价。',
      },
      quadruplet: { name: '四连音', desc: '组内四个音总共占 1 拍。' },
      explicitRatio: {
        name: '显式连音比例',
        desc: '用 实际数:常规数; 指定比例，适用于组内时值无法推导比例的情况。',
      },
      slur: {
        name: '连音线',
        desc: '在前一个音前写 ( 标记起点，在后一个音后写 ) 标记终点；可跨小节。',
      },
    },
    measures: {
      chord: { name: '和弦', desc: '多个音高同时发声，并在谱面上纵向排列。' },
      chordDuration: { name: '带时值和弦', desc: '这个和弦持续 1/2 拍。' },
      barline: { name: '小节线', desc: '结束当前小节。' },
      doubleBarline: {
        name: '双小节线',
        desc: '与 | 等效；渲染时最后一小节自动显示终止线。',
      },
      repeat: { name: '反复记号', desc: '分别表示反复段落的起点和终点。' },
      repeatBar: {
        name: '重复小节',
        desc: '当前内容重复 2 次，小节号相应增加。',
      },
      multiRepeat: { name: '多次重复', desc: '当前内容重复 10 次。' },
      voice: {
        name: '声线分隔（复调）',
        desc:
          '复调小节内先写第 1 声线，再写 & 和第 2 声线；各声线从小节起点独立计时。例：0 1 2 3 & w1, |。',
      },
    },
    expression: {
      ppp: { name: '弱力度', desc: '从极弱到弱，p 为基本弱。' },
      mpMf: { name: '中弱与中强', desc: '表示介于弱和强之间的力度。' },
      ff: { name: '强力度', desc: '从强到极强，f 为基本强。' },
      fpSfz: {
        name: '强后弱与突强',
        desc: '强后弱、突强、突强后弱。',
      },
      sfFz: { name: '强调类力度', desc: '突强、强调、加强。' },
      staccatoAccentTenuto: {
        name: '断奏、重音、保持',
        desc: '分别表示 staccato、accent、tenuto。',
      },
      trillFermata: {
        name: '颤音、延音',
        desc: '颤音 trill、延音记号 fermata。',
      },
      tremolo: {
        name: '颤弓/轮指/摇指',
        desc: 'tremolo（三道斜线），仅 erhu/ruan/guzheng 可用。',
      },
      slide: {
        name: '连线滑音',
        desc: '写在目标音前，连接前一个音；古筝模式自动判断上滑或下滑。',
      },
      measureLevelShorthand: {
        name: '小节级简写',
        desc: '写在小节开头，对该小节所有音符与和弦生效，休止符不继承。',
      },
      comment: { name: '注释', desc: '从双斜线开始忽略到当前行末尾。' },
    },
    lyrics: {
      block: {
        name: '歌词块',
        desc: '全文唯一，写在简谱正文之后、/L: 独占行首；| 与谱面逐小节对齐，可少写不能多写；时值超出小节的词不显示。',
      },
      streams: {
        name: '歌词流',
        desc: '小节内用 & 分隔多条歌词流，各流独立计时；每小节流数量必须一致，槽位可留空。',
      },
      duration: {
        name: '歌词时值',
        desc: '词项默认占一拍；q/s/d/h/w 前缀分别为 1/2、1/4、1/8、2、4 拍。英文词以这些字母开头时整词保留（如 star）。',
      },
      placeholder: {
        name: '时值占位',
        desc: '空拍写为时值前缀加 0（如 q0），推进该流时间但不显示歌词；前缀不能单独出现。',
      },
      multiLine: {
        name: '多行书写',
        desc: '块内换行等同空白，推荐每行一个小节；不能写 // 注释，/、|、& 为保留符号。',
      },
    },
  },

  // 速查表
  quickRef: {
    scale: { name: '音级 / 休止符', desc: '数字直接输入。' },
    octave: { name: '高 / 低八度', desc: '写在音级数字后，可叠加。' },
    accidental: {
      name: '变音',
      desc: '升、降、重升、重降、还原（可前置或后置；还原仅前缀）。',
    },
    microtone: {
      name: '微音程',
      desc: '四分之一升/降、四分之三升/降（仅前缀）。',
    },
    durationPrefix: {
      name: '时值前缀',
      desc: '全、二分、四分、八分、十六分、三十二分、六十四分音符。',
    },
    dotExtend: {
      name: '附点 / 延长线',
      desc: '附点延长一半（写在音级后），- 每个延长一拍。',
    },
    tie: {
      name: '延音线',
      desc: '起点（音符后）/ 终点（音符前），跨小节自动传播。',
    },
    slur: { name: '连音线', desc: '前缀 ( 标记起点，后缀 ) 标记终点。' },
    groupRepeat: {
      name: '连音组 / 重复',
      desc: '$ 包裹连音组（紧凑或空格分隔），*N 重复当前小节 N 次。',
    },
    explicitRatio: { name: '显式连音比例', desc: '实际数:常规数; 指定比例。' },
    chord: { name: '和弦', desc: '方括号内 + 分隔，可加时值前缀。' },
    barStructure: {
      name: '小节结构',
      desc: '小节线、双小节线、反复记号。',
    },
    voice: {
      name: '声线分隔',
      desc: '复调小节内分隔并行旋律线；每条声线从小节起点独立计时。',
    },
    dynamics: { name: '力度', desc: '16 种力度标记，\\ 加符号。' },
    articulation: {
      name: '演奏法',
      desc: '断奏、重音、颤音等，^ 加标记。',
    },
    folk: {
      name: '民乐标记',
      desc: '颤弓/轮指/摇指（^l）、连线滑音（^lh），仅 erhu/ruan/guzheng。',
    },
    measureLevel: {
      name: '小节级标记',
      desc: '括号包裹，写在小节开头。',
    },
    instrument: {
      name: '乐器模式',
      desc: '普通、二胡、阮或古筝（zhongruan 同 ruan）。',
    },
    lyricComment: {
      name: '歌词 / 注释',
      desc: '歌词块 /L: .../ 按小节对齐；| 划分歌词小节，& 分隔歌词流，可跨行书写。',
    },
    partPage: {
      name: '分谱 / 分页',
      desc: '多声部或多页输入标记。',
    },
  },

  // 提示消息
  message: {
    exampleCopied: '示例已复制',
    copyFailed: '复制失败，请稍后重试',
  },
}

export default syntax
