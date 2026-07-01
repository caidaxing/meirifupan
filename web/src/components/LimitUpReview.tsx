import type { ReviewData } from '../types'
import { ReviewWorkbench } from './review/ReviewWorkbench'

interface Props {
  data: ReviewData
}

export function LimitUpReview({ data }: Props) {
  return <ReviewWorkbench date={data.date} />
}
