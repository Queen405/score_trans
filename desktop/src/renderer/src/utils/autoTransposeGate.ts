// 自动转调的纯状态机：负责「用哪个基线、发不发请求、收不收响应」。
//
// 拆出这一层的原因：真正容易出错的是基线时机与竞态，而这些逻辑放在 .vue 里
// 无法被 test:utils 覆盖。组件只保留 setTimeout 接线，判断全部下沉到这里。
//
// 基线（baseline）语义：一串连击编辑中「最早一次编辑之前」的文本。转调必须以
// 它为旧调来源，否则用户刚敲下的新调号会被当成旧调，导致检测不到变化。
//
// 基线只在「一次请求确实产生了改动」后才丢弃（commitRequest）。判定不发请求、
// 或后端跳过/报错/无变化时都要把它留住（rollbackRequest），因为打字过程中会经过
// 大量中间态：1=C 删成 1= 再打成 1=D、1=E 补上空格前不是独立 token。若在这些
// 中间态上消耗基线，最初那个合法的「编辑前文本」就丢了，真正的换调再也拿不到旧调。

import type { KeyEditVerdict } from './jianpuTranspose'

export interface AutoTransposeRequest {
  baseline: string
  text: string
}

/** 判定一次编辑的调号变化类型。由调用方注入，便于单测。 */
export type KeyEditClassifier = (oldText: string, newText: string) => KeyEditVerdict

export class AutoTransposeGate {
  private baseline: string | null = null
  private latest: string | null = null
  /** 已借出给在途请求的基线；请求失败时还回 baseline。 */
  private dispatched: string | null = null
  private requestId = 0

  constructor(private readonly classifyKeyEdit: KeyEditClassifier) {}

  /**
   * 记录一次编辑。
   *
   * @param before 编辑前的文本（组件里取 props.modelValue，此刻尚未被 emit 覆盖）
   * @param after  编辑后的文本
   */
  recordEdit(before: string, after: string): void {
    if (this.baseline === null) this.baseline = before
    this.latest = after
  }

  /**
   * debounce 到期时调用，取出待发请求。
   *
   * transposable（改调号/加调号）与 key-removed（调号被删干净）才借出并清空
   * baseline；unchanged / no-key 时保留 baseline，让它活到用户真正把调号敲完整。
   *
   * @param currentText 当前真实文本；与记录的 latest 不一致说明期间被外部覆盖
   *                    （切页、历史恢复等），此次编辑作废。
   */
  takePending(currentText: string): AutoTransposeRequest | null {
    const baseline = this.baseline
    const latest = this.latest
    if (baseline === null || latest === null) return null
    // 文档被外部换掉，旧基线确实无效，连同 latest 一起丢弃。
    if (latest !== currentText) {
      this.baseline = null
      this.latest = null
      return null
    }
    if (baseline === latest) {
      this.baseline = null
      this.latest = null
      return null
    }
    const verdict = this.classifyKeyEdit(baseline, latest)
    if (verdict !== 'transposable' && verdict !== 'key-removed') return null
    this.baseline = null
    this.latest = null
    this.dispatched = baseline
    return { baseline, text: latest }
  }

  /** 发起请求，返回用于校验响应新鲜度的 id。 */
  beginRequest(): number {
    this.requestId += 1
    return this.requestId
  }

  /** 转调结果已应用：借出的基线可以丢弃了。 */
  commitRequest(): void {
    this.dispatched = null
  }

  /**
   * 判断一个响应是否应当被应用。
   *
   * @param id            beginRequest 返回的 id
   * @param requestedText 发请求时的文本
   * @param currentText   当前真实文本
   */
  acceptResponse(id: number, requestedText: string, currentText: string): boolean {
    if (id !== this.requestId) return false
    return requestedText === currentText
  }

  /**
   * 请求没能产生改动（后端跳过、报错、或返回原文）：把借出的基线还回去，
   * 让用户接下来的编辑仍能拿到那个「编辑前的合法文本」作旧调来源。
   *
   * 若期间用户已敲入新的编辑，其 baseline 更接近当前文档，保留它而非覆盖。
   *
   * @param id beginRequest 返回的 id。已被更新请求取代时不做任何事——此刻
   *           dispatched 属于那个更新的请求，还回去会污染它的基线。
   */
  rollbackRequest(id?: number): void {
    if (id !== undefined && id !== this.requestId) return
    if (this.dispatched === null) return
    if (this.baseline === null) this.baseline = this.dispatched
    this.dispatched = null
  }

  /** 丢弃待发编辑，并让所有在途响应失效（关闭开关、卸载、外部覆盖时调用）。 */
  reset(): void {
    this.baseline = null
    this.latest = null
    this.dispatched = null
    this.requestId += 1
  }

  /** 仅供测试与调试：是否持有可用作旧调来源的基线。 */
  get hasPendingEdit(): boolean {
    return this.baseline !== null
  }
}
