import type zhSyntax from '../zh-CN/syntax'

const syntax: typeof zhSyntax = {
  // Sidebar / page header
  eyebrow: 'Syntax Reference',
  heading: 'Syntax Guide',
  searchPlaceholder: 'Search syntax, names, or descriptions',
  sectionNavLabel: 'Syntax sections',
  searchAriaLabel: 'Search numbered-notation syntax',

  // Section navigation
  section: {
    quickStart: 'Quick Start',
    metadata: 'Score Metadata',
    notes: 'Notes & Octaves',
    duration: 'Durations & Tuplets',
    measures: 'Chords & Measures',
    expression: 'Dynamics & Annotations',
    lyrics: 'Lyrics',
    performanceMarks: 'Performance Techniques',
    quickReference: 'Quick Reference',
  },

  // Search results
  search: {
    kicker: 'Search Results',
    resultCount: 'Found {count} matching syntax entries',
    clear: 'Clear search',
    empty: 'No matching syntax found',
    backToFull: 'Back to full guide',
  },

  // Code block
  codeBlock: {
    notation: 'Numbered Notation',
    copied: 'Copied',
    copy: 'Copy example',
  },

  // Table headers
  table: {
    syntax: 'Syntax',
    meaning: 'Meaning',
    descOrExample: 'Notes or Example',
    note: 'Remarks',
    technique: 'Technique',
    notationNote: 'Notation Notes',
  },

  // Performance techniques (runtime data)
  profiles: {
    loading: 'Loading performance techniques',
    errorTitle: 'Performance techniques unavailable',
    retry: 'Reload',
    empty: 'No instrument syntax available',
    meta: 'Score Metadata',
    noTechnique: 'No exclusive techniques for this mode',
    range: 'Range Notation',
    combination: 'Combination Examples',
    techniquesSuffix: ' Techniques',
    error: 'Please confirm the backend service is running and try again.',
  },

  // Syntax section titles and kickers
  sections: {
    metadata: { title: 'Score Metadata', kicker: 'Document Settings' },
    notes: { title: 'Notes & Octaves', kicker: 'Pitch' },
    duration: { title: 'Durations & Tuplets', kicker: 'Rhythm' },
    measures: { title: 'Chords & Measures', kicker: 'Structure' },
    expression: {
      title: 'Dynamics & Annotations',
      kicker: 'Text & Expression',
    },
    lyrics: { title: 'Lyrics', kicker: 'Lyrics & Alignment' },
  },

  // Quick start search item
  quickStartExample: {
    groupTitle: 'Quick Start',
    sectionTitle: 'Quick Start',
    name: 'Quick Start Example',
    description:
      'Bach two-part invention, with multiple pages (@page), voices (@part), key signature, time signature, tempo, dotted notes, ties, dynamics, and articulation marks.',
  },

  // Lyric section example titles
  lyricExamples: {
    basic: 'Basic Alignment',
    streams: 'Multiple Verses & Line Breaks',
  },

  // Syntax section entries
  entries: {
    metadata: {
      keySignature: { name: 'Key Signature', desc: 'Uses C as the tonal center.' },
      timeSignature: {
        name: 'Time Signature',
        desc: 'Four beats per measure, quarter note gets one beat.',
      },
      midwayKeyChange: {
        name: 'Mid-score Key Change',
        desc: 'Written before a measure’s notes; subsequent measures switch to G. Cannot be written after notes.',
      },
      midwayMeterChange: {
        name: 'Mid-score Meter Change',
        desc: 'Written before a measure’s notes; subsequent measures switch to 3/4.',
      },
      title: { name: 'Score Title', desc: 'Optional, shown at the top of the score.' },
      instrument: {
        name: 'Instrument Mode',
        desc: 'Use general, erhu, ruan, or guzheng; zhongruan is also accepted as an alias of ruan.',
      },
      tempo: {
        name: 'Tempo',
        desc: 'An integer BPM from 20–300; defaults to 120 when omitted.',
      },
      midwayTempo: {
        name: 'Mid-score Tempo Change',
        desc: 'On its own line before the first note of the target measure, applying to that measure and those after.',
      },
    },
    notes: {
      scaleDegree: { name: 'Scale Degrees', desc: 'Represent do through si.' },
      rest: { name: 'Rest', desc: 'Holds duration but produces no sound.' },
      octaveUp: {
        name: 'Octave Up',
        desc: 'Add an apostrophe after the digit; displayed with an over-dot.',
      },
      octaveDown: {
        name: 'Octave Down',
        desc: 'Add a comma after the digit; displayed with an under-dot.',
      },
      accidentalSharpFlat: {
        name: 'Sharp / Flat',
        desc: 'Write a sharp or flat before the degree, or after (e.g. 1#, 7b).',
      },
      doubleAccidental: {
        name: 'Double Sharp / Flat',
        desc: 'Raise or lower by two semitones; may be prefixed or suffixed.',
      },
      natural: {
        name: 'Natural',
        desc: 'Cancels a previous accidental; prefix only.',
      },
      quarterAccidental: {
        name: 'Quarter Sharp / Flat',
        desc: 'Microtone, raise or lower by half a semitone; prefix only.',
      },
      threeQuarterAccidental: {
        name: 'Three-quarter Sharp / Flat',
        desc: 'Microtone, raise or lower by one and a half semitones; prefix only.',
      },
    },
    duration: {
      whole: { name: 'Whole Note', desc: 'Lasts 4 beats.' },
      half: { name: 'Half Note', desc: 'Lasts 2 beats.' },
      quarter: { name: 'Quarter Note', desc: 'Lasts 1 beat; also the default.' },
      eighth: { name: 'Eighth Note', desc: 'Lasts 1/2 beat.' },
      sixteenth: { name: 'Sixteenth Note', desc: 'Lasts 1/4 beat.' },
      thirtySecond: { name: 'Thirty-second Note', desc: 'Lasts 1/8 beat.' },
      sixtyFourth: { name: 'Sixty-fourth Note', desc: 'Lasts 1/16 beat.' },
      shorter: {
        name: 'Shorter Durations',
        desc: 'Last 1/32, 1/64, 1/128 beat; each extra d halves the duration.',
      },
      dotted: {
        name: 'Dotted',
        desc: 'Extends the duration by half; must follow the degree, never between a duration prefix and the degree.',
      },
      fermata: {
        name: 'Extension Line',
        desc: 'Each dash adds one beat; may be stacked.',
      },
      tie: {
        name: 'Tie',
        desc: '5~ marks the start (after a note), ~5 marks the end (before a note); across a barline the next measure’s first note becomes the end automatically.',
      },
      triplet: {
        name: 'Triplet',
        desc: 'Compact form; the three notes in the group share 1 beat.',
      },
      tripletSpaced: {
        name: 'Space-separated Tuplet',
        desc: 'Equivalent to the compact form.',
      },
      quadruplet: {
        name: 'Quadruplet',
        desc: 'The four notes in the group share 1 beat.',
      },
      explicitRatio: {
        name: 'Explicit Tuplet Ratio',
        desc: 'Use actual:regular; to set the ratio when the group’s duration cannot be inferred.',
      },
      slur: {
        name: 'Slur',
        desc: 'Write ( before the previous note for the start and ) after the next note for the end; may cross barlines.',
      },
    },
    measures: {
      chord: {
        name: 'Chord',
        desc: 'Multiple pitches sound together, stacked vertically on the staff.',
      },
      chordDuration: {
        name: 'Chord with Duration',
        desc: 'This chord lasts 1/2 beat.',
      },
      barline: { name: 'Barline', desc: 'Ends the current measure.' },
      doubleBarline: {
        name: 'Double Barline',
        desc: 'Equivalent to |; the final measure auto-shows a final barline when rendered.',
      },
      repeat: {
        name: 'Repeat Marks',
        desc: 'Mark the start and end of a repeated passage, respectively.',
      },
      repeatBar: {
        name: 'Repeat Measure',
        desc: 'Repeats the current content 2 times; measure numbers increase accordingly.',
      },
      multiRepeat: { name: 'Multiple Repeats', desc: 'Repeats the current content 10 times.' },
      voice: {
        name: 'Voice Separator (Polyphony)',
        desc:
          'When multiple parallel melodic lines (polyphony) exist in one measure, write the entire first voice first, then & and the second voice; each voice is timed independently from the measure start. Example: 0 [1+3] [1+3] [1+3] & w1, |.',
      },
    },
    expression: {
      ppp: {
        name: 'Soft Dynamics',
        desc: 'From very soft to soft; p is the base soft mark.',
      },
      mpMf: {
        name: 'Mezzo Soft / Mezzo Forte',
        desc: 'Dynamics between soft and loud.',
      },
      ff: {
        name: 'Loud Dynamics',
        desc: 'From loud to very loud; f is the base loud mark.',
      },
      fpSfz: {
        name: 'Forte-piano & Sforzando',
        desc: 'Forte-piano, sforzando, sforzando-piano.',
      },
      sfFz: {
        name: 'Emphasis Dynamics',
        desc: 'Sforzato, emphasis, reinforced.',
      },
      staccatoAccentTenuto: {
        name: 'Staccato, Accent, Tenuto',
        desc: 'Represent staccato, accent, and tenuto, respectively.',
      },
      trillFermata: {
        name: 'Trill, Fermata',
        desc: 'Trill and fermata mark.',
      },
      tremolo: {
        name: 'Tremolo / Roll / Shake',
        desc: 'Tremolo (three slashes); available only for erhu/ruan/guzheng.',
      },
      slide: {
        name: 'Connected Glissando',
        desc: 'Written before the target note, connecting to the previous note; guzheng mode auto-decides up or down.',
      },
      measureLevelShorthand: {
        name: 'Measure-level Shorthand',
        desc: 'Written at the start of a measure, applying to all notes and chords in it; rests do not inherit it.',
      },
      comment: {
        name: 'Comment',
        desc: 'Ignored from the double slash to the end of the current line.',
      },
    },
    lyrics: {
      block: {
        name: 'Lyric Block',
        desc: 'Unique per document, written after the score body, and /L: must begin its line; | separates lyric measures, aligning with the score measure by measure — lyric measures may be fewer, never more. A word whose duration overflows its measure is not displayed, and the editor reports it.',
      },
      streams: {
        name: 'Lyric Streams',
        desc: 'Use & inside a measure to separate lyric streams; each stream keeps its own timing. Every lyric measure must have the same number of streams, and a slot may be left empty.',
      },
      duration: {
        name: 'Lyric Duration',
        desc: 'Each word takes one beat by default; the q/s/d/h/w prefixes make it 1/2, 1/4, 1/8, 2, and 4 beats, advancing only that stream. Latin words that start with these letters are kept whole (e.g. star, do).',
      },
      placeholder: {
        name: 'Duration Placeholder',
        desc: 'Write a rest as 0 with a duration prefix (e.g. q0 takes 1/2 beat) to advance the stream without showing a word; a bare prefix such as q or s is an error.',
      },
      multiLine: {
        name: 'Multi-line Writing',
        desc: 'Line breaks inside the block count as whitespace, so it may span multiple lines — one measure per line is recommended; // comments are not allowed inside, and / | & are reserved.',
      },
    },
  },

  // Quick reference
  quickRef: {
    scale: { name: 'Degrees / Rest', desc: 'Type the digits directly.' },
    octave: {
      name: 'Octave Up / Down',
      desc: 'Written after the degree digit; may be stacked.',
    },
    accidental: {
      name: 'Accidentals',
      desc: 'Sharp, flat, double sharp, double flat, natural (prefix or suffix; natural prefix only).',
    },
    microtone: {
      name: 'Microtones',
      desc: 'Quarter sharp/flat, three-quarter sharp/flat (prefix only).',
    },
    durationPrefix: {
      name: 'Duration Prefixes',
      desc: 'Whole, half, quarter, eighth, sixteenth, thirty-second, sixty-fourth notes.',
    },
    dotExtend: {
      name: 'Dot / Extension',
      desc: 'Dot extends by half (after degree); - adds one beat each.',
    },
    tie: {
      name: 'Tie',
      desc: 'Start (after note) / end (before note); propagates across barlines automatically.',
    },
    slur: { name: 'Slur', desc: 'Prefix ( marks start, suffix ) marks end.' },
    groupRepeat: {
      name: 'Tuplet / Repeat',
      desc: '$ wraps a tuplet group (compact or space-separated); *N repeats the current measure N times.',
    },
    explicitRatio: {
      name: 'Explicit Tuplet Ratio',
      desc: 'actual:regular; sets the ratio.',
    },
    chord: {
      name: 'Chord',
      desc: 'Inside brackets, + separated, duration prefix allowed.',
    },
    barStructure: {
      name: 'Bar Structure',
      desc: 'Barline, double barline, repeat marks.',
    },
    voice: {
      name: 'Voice Separator',
      desc: 'Separates parallel melodic lines in a polyphonic measure; each voice is timed from the measure start.',
    },
    dynamics: {
      name: 'Dynamics',
      desc: '16 dynamic marks, \\ followed by the symbol.',
    },
    articulation: {
      name: 'Articulation',
      desc: 'Staccato, accent, trill, etc., ^ followed by the mark.',
    },
    folk: {
      name: 'Folk Marks',
      desc: 'Tremolo/roll/shake (^l), connected glissando (^lh); erhu/ruan/guzheng only.',
    },
    measureLevel: {
      name: 'Measure-level Mark',
      desc: 'Wrapped in parentheses, written at the measure start.',
    },
    instrument: {
      name: 'Instrument Mode',
      desc: 'General, erhu, ruan, or guzheng (zhongruan same as ruan).',
    },
    lyricComment: {
      name: 'Lyric / Comment',
      desc: 'The /L: .../ lyric block aligns by measure; | separates lyric measures, & separates lyric streams, and the block may span multiple lines.',
    },
    partPage: {
      name: 'Part / Page',
      desc: 'Multi-voice or multi-page input markers.',
    },
  },

  // Toast messages
  message: {
    exampleCopied: 'Example copied',
    copyFailed: 'Copy failed, please try again',
  },
}

export default syntax
