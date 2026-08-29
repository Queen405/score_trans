// 自动转调的纯状态机：负责「用哪个基线、发不发请求、收不收响应」。
//
// 拆出这一层的原因：真正容易出错的是基线时机与竞态，而这些逻辑放在 .vue 里
// 无法被 test:utils 覆盖。组件只保留 setTimeout 接线，判断全部下沉到这里。
//
// 基线（baseline）语义：一串连击编辑中「最早一次编辑之前」的文本。转调必须以
// 它为旧调来源，否则用户刚敲下的新调号会被当成旧调，导致检测不到变化。

export interface AutoTransposeRequest {
  baseline: string
  text: string
}

/** 判断两段文本之间是否存在调号变化。由调用方注入，便于单测。 */
export type KeyChangePredicate = (oldText: string, newText: string) => boolean

export class AutoTransposeGate {
  private baseline: string | null = null
  private latest: string | null = null
  private requestId = 0

  constructor(private readonly hasKeyChange: KeyChangePredicate) {}

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
   * @param currentText 当前真实文本；与记录的 latest 不一致说明期间被外部覆盖
   *                    （切页、历史恢复等），此次编辑作废。
   */
  takePending(currentText: string): AutoTransposeRequest | null {
    const baseline = this.baseline
    const latest = this.latest
    this.baseline = null
    this.latest = null
    if (baseline === null || latest === null) return null
    if (latest !== currentText) return null
    if (baseline === latest) return null
    if (!this.hasKeyChange(baseline, latest)) return null
    return { baseline, text: latest }
  }

  /** 发起请求，返回用于校验响应新鲜度的 id。 */
  beginRequest(): number {
    this.requestId += 1
    return this.requestId
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

  /** 丢弃待发编辑，并让所有在途响应失效（关闭开关、卸载、外部覆盖时调用）。 */
  reset(): void {
    this.baseline = null
    this.latest = null
    this.requestId += 1
  }

  /** 仅供测试与调试：是否有待发编辑。 */
  get hasPendingEdit(): boolean {
    return this.baseline !== null
  }
}
